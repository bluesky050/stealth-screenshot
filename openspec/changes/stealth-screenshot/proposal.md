# Proposal

## Why

Windows 自带的截图工具（Win+Shift+S）和第三方截图软件在截屏时都会在屏幕上显示彩色选框、半透明遮罩或闪烁高亮，旁人从电脑屏幕上一眼就能看出"正在截图"。需要一个隐形截图工具：截屏过程在屏幕上无任何视觉痕迹，避免引起旁人注意。

## What Changes

- 新增 Windows 隐形截图工具，通过全局热键触发
- 鼠标拖选截图区域，拖选过程中屏幕不显示任何选框、遮罩、高亮或线条
- 截图完成后将图片直接写入系统剪贴板（CF_DIB / PNG 格式），用户可立即在任意应用中 Ctrl+V 粘贴
- 工具以轻量后台进程方式运行，无窗口、无托盘图标（或可选极简托盘）
- 截图区域由鼠标按下点到松开点的矩形决定，坐标精确到像素

## Capabilities

### New Capabilities
- `stealth-capture`: 隐形区域截图能力 — 全局热键触发，鼠标拖选区域，全程无可见选框，截取的图像直接进入系统剪贴板

### Modified Capabilities

（无 — 这是全新项目，无已有 specs）

## Impact

- 新项目，无已有代码受影响
- 依赖：Windows API（全局热键注册、鼠标钩子、屏幕捕获、剪贴板写入）
- 技术栈待定（design.md 中决策），候选方案包括 Python（pywin32 + Pillow）、Rust（windows-rs）、C#（WPF）
- 运行环境：Windows 10/11
- 产物：单一可执行文件或脚本，可开机自启
