---
name: do-history
description: 汇总和比较 digital-oracle（DO）的历史市场分析报告。用户问某主题过去几次判断如何变化、要看 DO 时间线或复盘旧结论时使用；新行情预测仍使用 digital-oracle。
---

# DO 历史复盘

项目根目录：`D:\Github\Agent\digital-oracle`。

1. 在项目目录运行 `python -m digital_oracle.timeline.cli import`，读取项目报告、坚果云 DO 归档和 Web 历史，更新本地索引；原文不得修改。若某来源不可用，明确列出遗漏来源。
2. 根据用户主题运行 `python -m digital_oracle.timeline.cli compare --subject <主题> --limit 100`。可选主题见 `python -m digital_oracle.timeline.cli list --subject <主题>`；必要时从原报告全文核对联合主题里的单项判断。
3. 回答按分析时间列出每份报告，区分主判断、主情景概率、监控阈值和数据口径的变化。每项变化给出原报告路径和关键原文依据。未知分析时间单列，不强行排进连续比较。
4. `待核对`、不同预测窗口、不同标的/合约或联合主题的单项结论不能直接算概率或价格差。不要用旧报告解释当前行情；用户要求最新走势时再调用 DO 取得新数据。
5. 浏览器页面为本地 DO Web 服务的 `/timeline`。如果用户想看可视化，可提示启动项目现有 Web 服务后访问 `http://127.0.0.1:5000/timeline`。

索引可人工校正：`python -m digital_oracle.timeline.cli correct --hash <完整哈希> --field <字段> --value <JSON值>`。仅在核对原文后校正；校正留有日志，再次导入不会覆盖。
