# Design

## Context

全新项目，无已有代码。目标是 Windows 10/11 上的隐形截图工具。核心约束：截图过程中屏幕零视觉反馈、截图直接进剪贴板、轻量后台运行。

## Goals / Non-Goals

**Goals:**
- 全局热键触发，鼠标拖选区域，全程无可见选框
- 截图直接写入系统剪贴板（CF_DIB + PNG）
- 高 DPI 旁路：按物理像素捕获
- 单一可执行文件，零运行时依赖，可开机自启
- 无窗口、无通知、无声音

**Non-Goals:**
- 不做图片编辑/标注功能
- 不做截图保存到文件（仅剪贴板）
- 不做跨平台（仅 Windows）
- 不做录屏/滚动截图
- 不做云端同步

## Decisions

### D1: 技术栈选 Python（pywin32 + Pillow + keyboard）

**选择**: Python 3.11 + pywin32 + Pillow + keyboard 库

**理由**:
- pywin32 直接调用 Win32 API：`RegisterHotKey`、`SetWindowsHookEx`（鼠标钩子）、`BitBlt`/`PrintWindow`（屏幕捕获）、`OpenClipboard`/`SetClipboardData`（剪贴板写入）
- Pillow 做图像裁剪和 PNG 编码
- keyboard 库提供简洁的全局热键注册，比手工 `RegisterHotKey` + 消息循环更可靠
- 开发速度快，用户机器上已有 Python 环境

**备选方案**:
- Rust（windows-rs）：性能最佳，单文件无依赖，但开发周期长，当前阶段优先功能可用
- C#（WPF）：天然 Windows 生态，但 `.NET` 运行时依赖较重，打包后体积大
- AutoHotkey：最轻量，但图像处理和剪贴板 PNG 写入能力有限

**后续可迁移**: 若性能或分发需求提升，核心逻辑可迁移到 Rust，当前 Python 版作为功能验证。

### D2: 隐形拖选实现 — 不创建透明窗口

**选择**: 直接用低级鼠标钩子（`WH_MOUSE_LL`）捕获按下/拖动/松开事件，不创建任何 overlay 窗口

**理由**:
- 即使是"透明"窗口也会在屏幕上产生微弱视觉变化（DWM 合成边缘、焦点切换闪烁）
- `WH_MOUSE_LL` 钩子可以在不创建任何窗口的情况下全局监听鼠标事件
- 鼠标按下时记录 `GetCursorPos`，松开时再取一次 `GetCursorPos`，两点确定矩形

**备选方案**:
- 创建全屏透明 layered 窗口（WS_EX_LAYERED + WS_EX_TRANSPARENT）：可捕获鼠标但 DWM 合成会有视觉痕迹，放弃
- 用 `GetAsyncKeyState` 轮询鼠标按键状态：精度差、CPU 浪费

### D3: 屏幕捕获 — BitBlt + DPI 旁路

**选择**: `BitBlt` 从屏幕 DC 复制到内存 DC，DPI 感知设为 per-monitor-v2

**理由**:
- `BitBlt` 是最快的屏幕像素复制方式
- 设置 `SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)` 后，坐标和尺寸按物理像素，不受系统缩放影响
- 虚拟屏幕坐标用 `GetSystemMetrics(SM_XVIRTUALSCREEN)` / `SM_YVIRTUALSCREEN` / `SM_CXVIRTUALSCREEN` / `SM_CYVIRTUALSCREEN` 处理多显示器

**备选方案**:
- Windows.Graphics.Capture API：支持 HDMI 内容捕获，但需要创建 WIC/Eumerator 对象，引入大量 COM 互操作复杂度，且会显示捕获指示器（与隐形目标冲突）
- `PrintWindow`：针对特定窗口而非区域，不适用

### D4: 剪贴板写入 — CF_DIB + PNG 双格式

**选择**: 用 `OpenClipboard` → `EmptyClipboard` → 写入 `CF_DIB` 和注册格式 `CF_PNG`

**理由**:
- `CF_DIB` 是 Windows 剪贴板原生位图格式，几乎所有应用都支持粘贴
- PNG 格式保留无损画质，现代应用（微信、QQ、Telegram、Office）优先读取 PNG
- 双格式写入确保最大兼容性

**实现路径**:
1. Pillow 裁剪图像 → `img.tobytes()` 得到原始像素
2. 构造 `BITMAPINFO` + `BITMAPINFOHEADER` + 像素数据 → 写入 `CF_DIB`
3. `img.save(buf, format='PNG')` → 写入注册格式 `RegisterClipboardFormat('PNG')`

### D5: 进程形态 — 无窗口 + 可选托盘

**选择**: 用 `pythonw.exe` 运行（无控制台窗口），通过 `python -m PyInstaller` 打包为单个 exe

**理由**:
- `pythonw.exe` 不创建控制台窗口
- PyInstaller `--onefile --noconsole` 打包为单一 exe，用户无需安装 Python
- 可选托盘图标用 `pystray` 库，默认关闭

### D6: 热键配置

**选择**: 读取同目录下 `config.json`，默认 `Ctrl+Alt+Q`

**格式**:
```json
{
  "hotkey": "ctrl+alt+q",
  "tray_icon": false
}
```

## Risks / Trade-offs

- [鼠标钩子被反作弊软件拦截] → 部分游戏或安全软件可能阻止 `WH_MOUSE_LL`，文档中注明此限制，不可完全规避
- [DPI 感知模式需要 manifest 或 API 调用] → 在入口处调用 `SetProcessDpiAwarenessContext`，PyInstaller 打包时嵌入 DPI manifest
- [PyInstaller 单文件启动较慢（解包临时目录）] → 可接受，截图工具不需要毫秒级冷启动
- [Python 进程内存占用比 Rust 大] → 约 15-25MB，可接受
- [Windows.Graphics.Capture 受限内容无法捕获] → `BitBlt` 也无法捕获受 DRM 保护的内容（如 Netflix），这是系统限制

## Open Questions

- 是否需要支持多显示器分别截图（而非跨屏矩形）？当前设计支持跨屏矩形，单屏子矩形是自然子集。留待用户反馈后决定是否扩展。
