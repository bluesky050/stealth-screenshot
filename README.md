# Stealth Screenshot

一个运行在 Windows 上的轻量区域截图工具。按下快捷键后，用鼠标拖出截图区域，松开左键即可将图片写入剪贴板。选区过程中不绘制遮罩或选框，并拦截本次鼠标点击，避免触发桌面的蓝色拖选框。

## 使用方法

1. 启动程序，同一时间只运行一个实例。
2. 按 **Ctrl+Q**，然后松开键盘。
3. 在截图区域的一个角按住鼠标左键，移动至对角，再松开左键。
4. 在微信、Word 等支持图片粘贴的应用中按 **Ctrl+V**。
5. 通过系统托盘图标的右键菜单选择“退出”。

没有可见选框是预期行为。宽度或高度不足 5 像素的区域会被忽略；每次截图前都需要重新按快捷键。截图成功后会替换当前剪贴板内容，程序不自动保存图片文件。

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
  mouse_hook.py     拖选坐标和截图点击拦截
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
.\.venv\Scripts\python.exe -m unittest test_hook_startup test_mouse_suppression -v
```

测试覆盖原生键盘/鼠标钩子的启动与退出、截图点击拦截以及普通点击透传。用户已于 2026-09-18 确认当前交互测试完成。多显示器、高 DPI、录屏观察和无 Python 机器部署仍需分别验收，不能由单元测试结果推断。

## 当前限制

- 仅支持 Windows；不保证能捕获受保护的视频或安全桌面。
- 尚无单实例保护，请先退出旧版本再启动新版本。
- 尚无独立的 Esc 取消选区操作。
- 截图处理在鼠标钩子回调中执行，大区域截图可能影响响应。
- 本工具不绘制截图选框，但不保证鼠标指针、托盘图标或前台应用完全没有任何视觉变化。
