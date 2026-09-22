# Stealth Screenshot

一个运行在 Windows 上的轻量区域截图工具。按下快捷键后，用鼠标拖出截图区域，松开左键即可将图片写入剪贴板。选区过程中不绘制遮罩或选框。快捷键触发后，覆盖所有显示器的近乎透明输入窗口接收拖选；松开后先隐藏窗口，再截图并写入剪贴板。

## 使用方法

1. 启动程序，同一时间只运行一个实例。
2. 按 **Ctrl+Q**，然后松开键盘。
3. 在截图区域的一个角按住鼠标左键，移动至对角，再松开左键。
4. 在微信、Word 等支持图片粘贴的应用中按 **Ctrl+V**。
5. 通过系统托盘图标的右键菜单选择“退出”。

没有可见选框是预期行为。按 Esc 或鼠标右键可取消选区，30 秒无操作会自动取消。宽度或高度不足 5 像素的区域会被忽略；每次截图前都需要重新按快捷键。截图成功后会替换当前剪贴板内容，程序不自动保存图片文件。

## 从源码运行

运行环境：Windows 10/11、Python 3.10 或更高版本。开发与打包使用过 Python 3.11。

在项目根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m stealth_screenshot
```

若不希望显示控制台，可使用虚拟环境中的 `pythonw.exe -m stealth_screenshot`。

## 配置

源码运行时读取项目根目录的 `config.json`：

```json
{
  "hotkey": "ctrl+q",
  "quit_hotkey": "ctrl+alt+shift+q",
  "tray_icon": false
}
```

- `hotkey`：截图快捷键，当前配置为 Ctrl+Q。删除配置文件后代码默认使用 Ctrl+Alt+Q。
- `quit_hotkey`：预留的退出组合键。当前热键匹配允许额外修饰键，与截图热键存在重叠，建议使用托盘菜单退出。
- `tray_icon`：当前版本仍会启动托盘图标，该配置尚未生效。

修改配置后需要重启。单文件 EXE 会读取打包时内嵌的配置，更改配置需要重新打包。支持 Ctrl、Alt、Shift 和字母组合；快捷键可能与前台应用冲突。

## 构建 EXE

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --onefile --noconsole --name stealth-screenshot --paths . --add-data "config.json;." --hidden-import pystray._win32 stealth_screenshot/__main__.py
```

输出为 `dist/stealth-screenshot.exe`。仓库保存源码，不提交本机生成的 EXE、构建缓存或日志。

## 实现结构

```text
stealth_screenshot/
  main.py           启动、配置和托盘菜单
  hotkey.py         全局键盘钩子
  input_overlay.py 全屏输入窗口、拖选与取消
  mouse_hook.py     旧鼠标钩子实现，主流程不再使用
  win32_hooks.py    64 位兼容的 Windows 钩子接口声明
  controller.py     截图流程协调
  screen_capture.py Windows GDI 屏幕捕获
  clipboard.py      CF_DIB 和 PNG 剪贴板写入
  config.py         配置加载
openspec/           设计、规格和验收任务
```

## 验证

在 Windows 上运行不注入键鼠输入、不覆盖剪贴板的回归测试：

```powershell
.\.venv\Scripts\python.exe -m unittest test_input_overlay test_input_overlay_native test_diagnostics test_hook_startup test_mouse_suppression -v
```

测试覆盖新窗口的启动与销毁、负坐标、重复按下、Esc 取消和隐藏先于截图回调。原有钩子测试仍保留。用户于 2026-09-22 在 VMware 窗口完成实际拖选验收。

## 当前限制

- 仅支持 Windows；不保证能捕获受保护的视频或安全桌面。
- 尚无单实例保护，请先退出旧版本再启动新版本。
- 输入窗口使用 1/255 不透明度：完全透明的 Windows 分层窗口会让鼠标事件穿透，因此不能保证画面像素完全不变。
- 截图在输入窗口线程中执行，大区域截图可能短暂影响下一次响应。
- 截图工具无法截取 Windows 安全桌面或受保护的视频；其他 VMware 版本或受保护画面的表现可能不同。
