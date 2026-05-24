"""Digital Oracle Web Dashboard — Flask application."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from flask import Flask, Response, jsonify, render_template, request, send_file

# Load .env file before anything else
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Ensure project root on sys.path so digital_oracle can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.db import delete_history_item, get_history, get_history_item, init_db, insert_question, save_report, update_status
from web.fetcher import run_fetch
from web.analysis import generate_report, _is_llm_configured, AVAILABLE_MODELS, DEFAULT_MODEL

# ---------------------------------------------------------------------------
# In-memory registry for active SSE streams
# ---------------------------------------------------------------------------
_streams: dict[str, Queue] = {}
_streams_lock = threading.Lock()


def _create_stream(qid: str) -> Queue:
    q: Queue = Queue()
    with _streams_lock:
        _streams[qid] = q
    return q


def _remove_stream(qid: str) -> None:
    with _streams_lock:
        _streams.pop(qid, None)


def _get_stream(qid: str) -> Queue | None:
    with _streams_lock:
        return _streams.get(qid)


# ---------------------------------------------------------------------------
# Background analysis workflow
# ---------------------------------------------------------------------------

def _run_workflow(qid: str, question: str, model: str) -> None:
    queue = _get_stream(qid)
    if queue is None:
        return

    try:
        update_status(qid, "fetching")

        # Step 1-2: Fetch data from providers
        results = run_fetch(question, queue)

        # Step 3: Generate report (either LLM or raw)
        report = generate_report(question, results, queue, model=model)

        save_report(qid, report)
        queue.put({"event": "done", "data": {
            "id": qid, "status": "done",
            "llm_used": _is_llm_configured(),
            "model": model if _is_llm_configured() else None,
        }})

    except Exception as exc:
        update_status(qid, "error", str(exc))
        queue.put({"event": "error", "data": {"id": qid, "status": "error", "message": str(exc)}})
    finally:
        _remove_stream(qid)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent / "static"),
    )

    init_db()

    # ---- Page routes ----

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            llm_configured=_is_llm_configured(),
            available_models=AVAILABLE_MODELS,
            default_model=DEFAULT_MODEL,
        )

    # ---- API routes ----

    @app.route("/api/question", methods=["POST"])
    def api_question():
        data = request.get_json()
        if not data or "question" not in data:
            return jsonify({"error": "missing 'question' field"}), 400

        question = data["question"].strip()
        if not question:
            return jsonify({"error": "question is empty"}), 400

        model = data.get("model", DEFAULT_MODEL)
        if model not in AVAILABLE_MODELS:
            model = DEFAULT_MODEL

        qid = insert_question(question)
        _create_stream(qid)

        thread = threading.Thread(target=_run_workflow, args=(qid, question, model), daemon=True)
        thread.start()

        return jsonify({"id": qid, "status": "pending", "model": model})

    @app.route("/api/question/<qid>/stream")
    def api_stream(qid: str):
        queue = _get_stream(qid)
        if queue is None:
            history = get_history_item(qid)
            if history and history.get("report"):
                def replay():
                    yield f"event: chunk\ndata: {json.dumps({'text': history['report']})}\n\n"
                    yield f"event: done\ndata: {json.dumps({'id': qid, 'status': 'done'})}\n\n"
                return Response(_sse(replay()), mimetype="text/event-stream")
            return jsonify({"error": "stream not found"}), 404

        def generate():
            heartbeat = time.time()
            while True:
                try:
                    msg = queue.get(timeout=5)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                    heartbeat = time.time()
                    if msg["event"] in ("done", "error"):
                        break
                except Empty:
                    now = time.time()
                    if now - heartbeat > 15:
                        yield ": heartbeat\n\n"
                        heartbeat = now

        return Response(_sse(generate()), mimetype="text/event-stream")

    @app.route("/api/question/<qid>/report")
    def api_report(qid: str):
        item = get_history_item(qid)
        if not item:
            return jsonify({"error": "not found"}), 404
        return jsonify(item)

    @app.route("/api/question/<qid>/download")
    def api_download(qid: str):
        item = get_history_item(qid)
        if not item or not item.get("report"):
            return jsonify({"error": "report not available"}), 404

        safe_name = item["question"][:50].replace("/", "_").replace("\\", "_").replace(":", "_")
        import io
        report_bytes = item["report"].encode("utf-8")
        return send_file(
            io.BytesIO(report_bytes),
            mimetype="text/markdown; charset=utf-8",
            as_attachment=True,
            download_name=f"digital-oracle-{safe_name}.md",
        )

    @app.route("/api/history")
    def api_history():
        return jsonify(get_history())

    @app.route("/api/history/<qid>")
    def api_history_item(qid: str):
        item = get_history_item(qid)
        if not item:
            return jsonify({"error": "not found"}), 404
        return jsonify(item)

    @app.route("/api/history/<qid>", methods=["DELETE"])
    def api_history_delete(qid: str):
        if delete_history_item(qid):
            return jsonify({"ok": True})
        return jsonify({"error": "not found"}), 404

    return app


def _sse(generator):
    """Wrap a generator in SSE framing."""
    def framed():
        for line in generator:
            yield line
    return framed()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

AVAILABLE_MODEL_LIST = ", ".join(AVAILABLE_MODELS)

if __name__ == "__main__":
    app = create_app()
    print("")
    print("  Digital Oracle Web Dashboard")
    print("  http://127.0.0.1:5000")
    print("")
    if _is_llm_configured():
        print(f"  LLM: DeepSeek API configured")
        print(f"  Models: {AVAILABLE_MODEL_LIST}")
        print(f"  Default: {DEFAULT_MODEL}")
    else:
        print("  LLM: not configured")
    print("")
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
