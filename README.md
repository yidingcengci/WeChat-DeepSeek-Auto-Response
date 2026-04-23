# WeChat-DeepSeek-Auto-Response

> **声明：** 本项目 Fork 自 [WeChat-DeepSeek-Auto-Response](https://github.com/yidingcengci/WeChat-DeepSeek-Auto-Response)，原始作者为 **Lao Chou**。我们在原项目基础上进行了功能扩展和改进，核心视觉识别与自动回复逻辑归功于原作者。

基于视觉的非侵入式微信自动回复程序，零封号风险。通过 OCR 识别聊天内容，调用 AI 接口生成回复，模拟键鼠自动发送。

## 特性

- **区域选择**：点击屏幕选择截图区域（消息区 + 最新会话位置 + 输入框）
- **图像预处理**：增强对比度，提升 OCR 识别准确率
- **图像比较**：对比截图变化，避免重复处理
- **AI 自动回复**：支持 DeepSeek / 智谱 GLM 等 OpenAI 兼容接口
- **知识库驱动**：基于自定义知识库生成回复，支持产品信息、FAQ、成交话术等
- **AI 性格设定**：自定义 AI 的说话风格和人设
- **零封号风险**：纯视觉识别，不修改微信任何文件或注入进程
- **知识库编辑器**：提供图形界面，无需手写 JSON

## 快速开始（推荐 - 使用打包好的 EXE）

### 1. 下载文件

从 [Releases](../../releases) 下载最新版本，需要以下文件：

| 文件 | 说明 |
|------|------|
| `微信AI自动回复.exe` | 主程序 - 微信自动回复 |
| `基础配置.exe` | 工具 - 图形化配置 API、知识库等 |
| `knowledge_base.json` | 配置文件（API Key、知识库等） |

把这三个文件放在**同一个文件夹**下。

### 2. 配置 API Key

双击运行 `基础配置.exe`，进入左侧第一个模块 **🔑 API 配置**：

1. 选择 API 平台（智谱 GLM / DeepSeek / OpenAI / 通义千问 / 月之暗面）
2. 填入你的 **API Key**（密码框隐藏，可勾选显示）
3. 选择模型名称（支持一键选择常用模型）
4. 点击 **🔌 测试连接** 验证配置是否正确
5. 点 **💾 保存到文件** 保存配置

### 3. 编辑知识库

双击运行 `基础配置.exe`，界面左侧有 7 个模块：

1. **🔑 API 配置** - 大模型接口地址、API Key、模型名称（支持测试连接）
2. **📋 基本信息** - 品牌名、课程类型、目标客户、联系方式
3. **🎭 AI 性格** - 设定 AI 的说话风格（支持快速模板 + 自定义规则）
4. **📦 产品信息** - 课程/产品列表和优势
5. **❓ 常见问题** - 关键词匹配 + 回复内容
6. **💬 成交话术** - 引导试听、促成报名、应对犹豫、逼单话术
7. **⚠️ 注意事项** - 禁止回复的场景

编辑完成后点 **「💾 保存到文件」** 写入 `knowledge_base.json`。

### 4. 运行自动回复

双击 `微信AI自动回复.exe`，按提示依次点击屏幕上的 4 个位置：

1. 点击**消息内容区域**的左上角
2. 点击**消息内容区域**的右下角
3. 点击**左侧最新会话**的位置（用于切换聊天对象）
4. 点击**输入框**的位置

程序开始运行后会自动：
- 监控消息区域的变化
- OCR 识别新消息
- 根据知识库 + AI 生成回复
- 自动切换到新消息发送者并回复

---

## 从源码运行

### 环境要求

- Python 3.8+
- Windows 10/11

### 安装依赖

```bash
pip install pyautogui pyperclip pynput pillow easyocr opencv-python openai
```

### 运行主程序

```bash
python Auto_choose_new_sender.py
```

### 运行基础配置

```bash
python knowledge_editor.py
```

### 打包为 EXE

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包基础配置编辑器
pyinstaller --noconfirm --onefile --windowed --name "基础配置" knowledge_editor.py

# 打包主程序（附带知识库文件）
pyinstaller --noconfirm --onefile --windowed --name "微信AI自动回复" --add-data "knowledge_base.json;." Auto_choose_new_sender.py
```

打包后的 exe 在 `dist/` 目录下。

---

## 项目结构

```
WeChat-DeepSeek-Auto-Response/
├── Auto_choose_new_sender.py   # 主程序 - 微信AI自动回复（原始文件，已修改）
├── knowledge_editor.py         # 基础配置 GUI（新增文件）
├── sender_Win.py               # Windows 平台发送适配器（原始文件）
├── sender_macOS.py             # macOS 平台发送适配器（原始文件）
├── knowledge_base.json         # 配置文件（API、知识库等）
├── README.md
└── .gitignore
```

## 知识库配置说明

`knowledge_base.json` 支持以下模块：

```json
{
  "API配置": {
    "API URL": "https://open.bigmodel.cn/api/paas/v4",
    "API Key": "你的API密钥",
    "模型名称": "glm-4-flash"
  },
  "基本信息": {
    "品牌名称": "你的品牌",
    "课程类型": "产品类型",
    "目标客户": "客户群体",
    "联系方式": "联系信息"
  },
  "AI性格设定": {
    "人设描述": "AI 的整体风格描述",
    "性格规则": ["具体行为规则1", "具体行为规则2"]
  },
  "产品信息": {
    "课程列表": [{"名称": "", "价格": "", "时长": "", "特色": "", "适合人群": ""}],
    "课程优势": ["优势1", "优势2"]
  },
  "常见问题与回复": [
    {"关键词": ["关键词1", "关键词2"], "回复": "回复内容"}
  ],
  "成交话术": {
    "引导试听": ["话术1"],
    "促成报名": ["话术1"],
    "应对犹豫": ["话术1"],
    "逼单话术": ["话术1"]
  },
  "禁止回复的场景": ["场景1", "场景2"]
}
```

> **建议使用「知识库编辑器.exe」编辑此文件**，无需手写 JSON。

## 注意事项

- 确保已授权 AI 接口的 API 密钥（在「基础配置.exe」的 API 配置模块中设置）
- 运行期间不要移动微信窗口位置
- 程序基于纯视觉识别，不修改微信任何文件，零封号风险
- `knowledge_base.json` 需要和 exe 放在同一目录下

## 许可证

本项目遵循 [MIT License](LICENSE) 开源。

## 致谢与版权声明

### 原始项目

- **项目名称：** WeChat-DeepSeek-Auto-Response
- **原始作者：** Lao Chou (laochou6423@gmail.com)
- **原始仓库：** [yidingcengci/WeChat-DeepSeek-Auto-Response](https://github.com/yidingcengci/WeChat-DeepSeek-Auto-Response)
- **核心功能：** 基于 OCR 的微信消息识别、AI 回复生成、键鼠模拟发送、图像预处理与对比

### 本 Fork 的改动

在原始项目基础上，我们新增/修改了以下功能：

| 改动 | 说明 |
|------|------|
| 🔑 API 配置模块 | 支持在 GUI 中配置 API 地址、密钥、模型，支持一键测试连接 |
| 📋 基础配置 GUI (`knowledge_editor.py`) | 新增图形化配置工具，包含 API 配置、知识库编辑等 7 个模块 |
| 🎭 AI 性格设定 | 新增人设描述 + 性格规则列表，支持快速模板和自定义规则 |
| 📦 知识库驱动 | 基于 `knowledge_base.json` 的完整知识库系统（产品/FAQ/话术/规则） |
| 🖥️ 打包为 EXE | PyInstaller 打包，Windows 用户无需安装 Python 即可使用 |

> 原始项目的核心代码（OCR 识别、自动回复逻辑、Windows/macOS 发送适配器等）版权归属原作者 Lao Chou。我们的改动部分同样以 MIT License 开源。
