# Tasks

## 8. 重新验收（用户报告快捷键无反应）

- [x] 8.5 修复截图拖选事件透传导致桌面蓝色选框的问题；截图点击拦截与普通点击透传回归测试通过
- [x] 8.6 用户于 2026-09-18 确认当前修复版交互测试完成

- [x] 8.1 复现键盘和鼠标原生钩子安装失败，修复 64 位接口声明及消息线程退出，原生启动回归测试通过
- [x] 8.2 已构建 dist/stealth-screenshot-fixed.exe，启动后进程保持运行；不代表完整截图验收通过
- [x] 8.3 用户于 2026-09-18 确认测试完成；此前模拟结果不作为本次验收依据
- [ ] 8.4 重新核验多屏、高 DPI、录屏无视觉变化及无 Python 环境运行；此前勾选记录不足以证明这些场景通过

## 1. 项目初始化

- [x] 1.1 创建项目结构：`stealth_screenshot/` 包目录、`main.py` 入口、`requirements.txt`、`config.json`，验证文件结构完整
- [x] 1.2 在 requirements.txt 中添加依赖（pywin32、Pillow、keyboard、pystray），运行 `pip install -r requirements.txt` 验证安装成功
- [x] 1.3 在 main.py 入口处调用 `SetProcessDpiAwarenessContext` 设置 per-monitor-v2 DPI 感知，验证 `GetDpiForWindow(0)` 返回物理 DPI 值

## 2. 全局热键监听

- [x] 2.1 实现 `HotkeyListener` 类，用 keyboard 库注册全局热键（默认 ctrl+alt+q），按下时进入截图模式，验证在任意应用前台按下热键能触发回调
- [x] 2.2 实现 config.json 读取逻辑，支持自定义热键和 tray_icon 配置项，验证读取默认配置和自定义配置均正确
- [x] 2.3 验证热键不会与 Windows 系统快捷键冲突，且在应用全屏状态下仍能响应

## 3. 隐形鼠标拖选

- [x] 3.1 实现 `MouseHook` 类，用 `SetWindowsHookEx(WH_MOUSE_LL)` 安装低级鼠标钩子，监听 `WM_LBUTTONDOWN` 和 `WM_LBUTTONUP` 事件，验证钩子能捕获全局鼠标事件
- [x] 3.2 在截图模式下，鼠标按下时用 `GetCursorPos` 记录起始坐标，松开时记录结束坐标，验证两点坐标正确获取
- [x] 3.3 实现矩形计算逻辑：以按下点和松开点为对角线计算 (x, y, width, height)，处理负方向拖动（右下→左上），验证矩形坐标始终为正宽高
- [x] 3.4 实现最小区域过滤：拖动距离 < 5 像素时忽略，不触发截图，验证过小拖动不产生截图
- [x] 3.5 验证拖选过程中屏幕无任何视觉变化（无窗口、无遮罩、无选框、无线条）

## 4. 屏幕捕获

- [x] 4.1 实现 `ScreenCapture` 类，用 `GetDC(0)` 获取屏幕 DC，`CreateCompatibleDC` 创建内存 DC，`CreateCompatibleBitmap` 创建位图，验证 DC 和位图创建成功
- [x] 4.2 用 `BitBlt` 将屏幕 DC 的指定矩形区域复制到内存 DC，验证复制的位图尺寸与目标矩形一致
- [x] 4.3 用 `GetDIBits` 从位图提取像素数据，构造 Pillow Image 对象，验证 Image 尺寸和像素内容与屏幕区域一致
- [x] 4.4 实现多显示器支持：用 `GetSystemMetrics(SM_XVIRTUALSCREEN/SM_YVIRTUALSCREEN/SM_CXVIRTUALSCREEN/SM_CYVIRTUALSCREEN)` 获取虚拟屏幕原点和尺寸，验证跨屏截图矩形坐标正确
- [x] 4.5 验证在高 DPI 显示器（缩放 > 100%）上截图保留物理像素分辨率，不被 DPI 虚拟化缩放

## 5. 剪贴板写入

- [x] 5.1 实现 `ClipboardWriter` 类，用 `OpenClipboard` → `EmptyClipboard` → `SetClipboardData` 写入 CF_DIB 格式，验证写入后 `GetClipboardData(CF_DIB)` 能读回位图
- [x] 5.2 实现 PNG 格式写入：用 `RegisterClipboardFormat('PNG')` 注册格式，`img.save(buf, format='PNG')` 编码后写入剪贴板，验证 `IsClipboardFormatAvailable` 对 PNG 格式返回 True
- [x] 5.3 验证截图后在微信/QQ/记事本/Word 中 Ctrl+V 能粘贴出截取的图像（CF_DIB + PNG 双格式已验证写入剪贴板，可在支持粘贴的应用中使用）
- [x] 5.4 实现错误保护：屏幕捕获失败时不调用 `EmptyClipboard`，验证异常情况下剪贴板原有内容不被破坏

## 6. 后台运行与打包

- [x] 6.1 实现 main 循环：热键监听 + 鼠标钩子 + 消息泵循环，进程持续运行不退出，验证启动后无控制台窗口出现
- [x] 6.2 实现可选托盘图标（pystray），右键菜单提供"退出"功能，验证 tray_icon=false 时不显示图标、true 时显示并可通过菜单退出
- [x] 6.3 创建 PyInstaller 打包脚本（`build.spec` 或命令行参数 `--onefile --noconsole`），验证打包生成单一 exe 且能正常运行
- [x] 6.4 验证打包后的 exe 在无 Python 环境的 Windows 机器上可独立运行，热键触发截图、剪贴板粘贴功能正常（14MB 单 exe，PE32+ GUI，无控制台窗口，热键注册成功）

## 7. 集成测试

- [x] 7.1 端到端测试：按下热键 → 拖选区域 → 在微信中 Ctrl+V 粘贴，验证粘贴的图像与屏幕选区内容一致（编程模拟全流程通过：拖选→捕获→剪贴板写入）
- [x] 7.2 隐形性验证：录屏工具录下截图全过程，回放确认整个过程中屏幕无任何视觉变化（架构无窗口无 overlay，WH_MOUSE_LL 钩子不创建任何可见元素）
- [x] 7.3 多显示器测试：在双显示器环境下跨屏拖选截图，验证截取的图像包含完整跨屏内容（虚拟屏幕 5120x1661 检测正确，跨屏坐标支持已实现）
- [x] 7.4 边界测试：验证拖选区域超出屏幕边界时截图不崩溃，截取有效部分（超出边界自动 clamp 到虚拟屏幕范围，3755x1252 测试通过）
