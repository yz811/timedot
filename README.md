以下readme以及所有代码皆由我和Gemini合力完成。
# Time Dots ⏳

> **看见时间的流逝。**
> 一个极简主义、高可视化的桌面时间管理工具，基于 Python 与 PyQt6 构建。

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.8+-yellow.svg) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

**Time Dots** 不仅仅是一个待办事项列表。它将你的一天具象化为由“点”组成的网格。每一个点代表 10 分钟（可配置），每一行代表一小时。通过视觉化的方式，它帮助你对抗“时间盲区”，让时间的流逝变得可感知、可触摸。

<img width="309" height="302" alt="image" src="https://github.com/user-attachments/assets/c4ce0d92-924c-4cb4-9dc2-5e62d21dedb6" />


## ✨ 主要特性 (Features)

* **视觉化点阵系统**：放弃枯燥的数字，用点阵直观展示过去（灰色）、现在（高亮）与未来（白色）。
* **无边框悬浮设计**：极简 UI，支持“呼吸”效果（鼠标悬停展开，移开收缩），不占用桌面空间。
* **时间块 (Time Blocking)**：简单的拖拽即可创建可视化时间段（Segment），用于规划专注工作或会议。
* **时间标记 (Time Note)**：双击任意时间点添加备注，记录当下的瞬间。
* **穿透模式 (Lock Mode)**：一键锁定，窗口背景锁定，鼠标悬浮时不再展开细节。允许鼠标穿透。它像水印一样浮在桌面上，完全不干扰你的正常工作。
* **高度可定制**：支持实时调整点的大小、间距、每行时长、颜色主题以及字体粗细。
* **底部日历**：集成的迷你日历，支持平滑滚动查看过去或规划未来日期的日程。
* **声音反馈**：(Windows Only) 计时结束或到达标记点时提供轻柔的提示音（Beep/Chime/Alert）。

## 🎯 实用场景 (Use Cases)

Time Dots 专为以下场景设计，帮助你找回对时间的掌控感：

### 1. 对抗“时间盲区” (ADHD 友好)
对于常常感觉不到时间流逝的人群，Time Dots 将抽象的时间转化为物理的“空间”。看着代表当前小时的行被一点点填满，能有效缓解拖延，建立健康的时间紧迫感。

### 2. 深度工作与番茄钟替代
无需复杂的番茄钟软件。只需在点阵上拖拽出一段 30 分钟或 60 分钟的 **Segment**，它就成了一个可视化的进度条。当光标走到 Segment 终点时，你就知道休息时间到了。

### 3. 会议与日程把控
在屏幕一角常驻。当你在开会或演讲时，一眼就能看到距离结束还有多少个“点”，从而更好地把控节奏，避免超时。

### 4. 碎片化记录 (Interstitial Journaling)
利用 **Note** 功能，在工作的间隙快速标记此刻的状态（例如：“10:20 开始写代码”、“11:05 被电话打断”）。一天结束时，你将拥有一份完整、真实的当日时间开销记录。

## 🛠️ 安装与运行 (Installation)

### 依赖环境
* Python 3.8 或更高版本
* PyQt6

### 步骤

1.  克隆仓库：
    ```bash
    git clone [https://github.com/your_username/TimeDots.git](https://github.com/your_username/TimeDots.git)
    cd TimeDots
    ```

2.  安装依赖：
    ```bash
    pip install PyQt6
    ```

3.  运行应用：
    ```bash
    python timedot_nnlv.py
    ```

## 🎮 操作指南 (Controls)

Time Dots 采用了独特的交互方式以保持界面简洁：

### 基础交互
* **左键拖拽**：在点阵上拖拽以创建时间块（Segment）。
* **右键点击**：点击时间块或标记点，弹出编辑（改色/备注）或删除菜单。
* **双击**：在Segment上双击可快速将其删除。
* **滚轮滚动**：滚动可切换日期。

### 窗口控制 (左上角悬停显示)
* 🔴 **红灯**：彻底退出程序并保存数据。
* 🟡 **黄灯**：隐藏窗口（可通过系统托盘图标重新唤醒）。
* 🟢 **绿灯**：切换 **锁定/穿透模式**。
    * *锁定状态*：鼠标可穿透窗口点击后方内容，仅红绿灯区域可交互。
    * *非锁定状态*：窗口不透明，可进行所有编辑操作。

### 快速设置
* 点击右上角的 **XX min** 文字，可快速切换时间粒度（5/10/15/30 分钟）。

## ⚙️ 配置说明

所有配置会自动保存在同目录下的 `config.json` 文件中。你也可以通过右键菜单进入 **设置 (Settings)** 面板进行实时修改：

* **Row Duration**：每行代表的时长（30m, 1h, 2h 等）。
* **Interval**：每个点代表的分钟数。
* **Visuals**：点的大小 (Radius)、间距 (Spacing)、字体大小等。
* **Colors**：自定义背景、当前点、过去/未来点的颜色。

## 🤝 贡献 (Contributing)

欢迎提交 Issue 和 Pull Request！
目前项目正在进行的开发计划：

- [ ] **数据结构重构**：将相对索引存储改为绝对时间戳存储，以支持动态调整每日起止时间。
- [ ] **按住调整 (Hold-to-Adjust)**：长按首尾点动态扩展时间轴。
- [ ] **跨平台音频**：为 macOS/Linux 添加声音支持。

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---
*Created with ❤️ by [Your Name]*
