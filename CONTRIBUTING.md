# 贡献指南

感谢你改进“视频转 Live 图”。

## 开始之前

1. 从 main 创建功能分支。
2. 使用 Python 3.10–3.12 创建虚拟环境。
3. 安装 requirements-dev.txt。
4. 先运行完整测试，确认基线正常。

## 提交要求

- 新功能和错误修复应先添加能够失败的测试。
- 保持 Apple、Android、vivo 与 UI 模块边界清晰。
- 不提交 .venv、build、dist、release 或 verification。
- 不提交真实照片、视频、GPS、设备序列信息或聊天记录。
- 新增厂商兼容样本时，应提炼成最小脱敏夹具。
- 更新行为时同步修改 README、兼容性说明或 CHANGELOG。

## 验证

~~~powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_markdown_links.py
.\.venv\Scripts\python.exe scripts\check_repository.py
~~~

## 提交信息

使用简短、明确的提交信息，例如：

- feat: add device compatibility
- fix: retain probe worker
- docs: clarify Android transfer
- test: add malformed metadata coverage

贡献代码默认按 Apache License 2.0 授权。请保留 LICENSE、NOTICE 和现有版权声明。
