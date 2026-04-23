# -*- coding: utf-8 -*-
"""
知识库编辑器 v2 —— 让普通用户用图形界面编辑 knowledge_base.json
不需要懂 JSON 格式，填表单就行。
v2: 修复添加/删除时行号冲突问题，采用「数据驱动重绘」方案
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import sys


class KnowledgeEditor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("⚙️ 基础配置")
        self.root.geometry("780x700")
        self.root.minsize(720, 600)

        # 知识库数据
        self.data = {}
        self.json_path = ""

        self._build_ui()
        self._auto_load()

    # ─────────────────── UI 构建 ───────────────────

    def _build_ui(self):
        # 顶部工具栏
        toolbar = tk.Frame(self.root, bg="#f0f0f0", padx=8, pady=6)
        toolbar.pack(fill="x")

        self.path_label = tk.Label(toolbar, text="未加载文件", fg="#888", bg="#f0f0f0",
                                   font=("微软雅黑", 9))
        self.path_label.pack(side="left")

        btn_style = {"font": ("微软雅黑", 9), "padx": 10, "pady": 3, "bd": 0, "cursor": "hand2"}

        tk.Button(toolbar, text="📂 打开", bg="#4CAF50", fg="white", activebackground="#388E3C",
                  command=self._open_file, **btn_style).pack(side="right", padx=3)
        tk.Button(toolbar, text="💾 保存到文件", bg="#2196F3", fg="white", activebackground="#1976D2",
                  command=self._save_file, **btn_style).pack(side="right", padx=3)
        tk.Button(toolbar, text="📄 新建", bg="#FF9800", fg="white", activebackground="#F57C00",
                  command=self._new_file, **btn_style).pack(side="right", padx=3)

        # 主体：左侧导航 + 右侧内容
        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=5, pady=5)

        # 左侧导航
        nav_frame = tk.Frame(body, width=160, bg="#f5f5f5", relief="groove", bd=1)
        nav_frame.pack(side="left", fill="y", padx=(0, 5))
        nav_frame.pack_propagate(False)

        tk.Label(nav_frame, text="配置模块", font=("微软雅黑", 10, "bold"),
                 bg="#f5f5f5", pady=8).pack()

        self.nav_buttons = []
        modules = [
            ("🔑 API 配置", "API配置"),
            ("📋 基本信息", "基本信息"),
            ("🎭 AI性格", "AI性格设定"),
            ("📦 产品信息", "产品信息"),
            ("❓ 常见问题", "常见问题与回复"),
            ("💬 成交话术", "成交话术"),
            ("⚠️ 注意事项", "禁止回复的场景"),
        ]
        for text, key in modules:
            btn = tk.Button(nav_frame, text=text, font=("微软雅黑", 10),
                            anchor="w", padx=12, pady=6, relief="flat", bg="#f5f5f5",
                            activebackground="#e0e0e0", cursor="hand2",
                            command=lambda k=key: self._switch_module(k))
            btn.pack(fill="x", padx=4, pady=2)
            self.nav_buttons.append((key, btn))

        # 右侧内容区域（可滚动）
        self.content_frame = tk.Frame(body)
        self.content_frame.pack(side="left", fill="both", expand=True)

        # Canvas + Scrollbar
        self.canvas = tk.Canvas(self.content_frame, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 让内容跟随 canvas 宽度
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # 鼠标滚轮绑定
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # 当前模块
        self.current_module = None

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ─────────────────── 通用：清空内容区 ───────────────────

    def _clear_content(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

    # ─────────────────── 文件操作 ───────────────────

    def _auto_load(self):
        possible = [
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "knowledge_base.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json"),
        ]
        if hasattr(sys, '_MEIPASS'):
            possible.insert(0, os.path.join(sys._MEIPASS, "knowledge_base.json"))
        for p in possible:
            if os.path.exists(p):
                self._load_json(p)
                return

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="选择知识库文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(sys.argv[0]))
        )
        if path:
            self._load_json(path)

    def _new_file(self):
        if self.data and not messagebox.askyesno("新建", "当前有未保存的内容，确定新建吗？"):
            return
        self.data = {
            "API配置": {"API URL": "https://open.bigmodel.cn/api/paas/v4", "API Key": "", "模型名称": "glm-4-flash"},
            "基本信息": {"品牌名称": "", "课程类型": "", "目标客户": "", "联系方式": ""},
            "AI性格设定": {"人设描述": "", "性格规则": []},
            "产品信息": {"课程列表": [], "课程优势": []},
            "常见问题与回复": [],
            "成交话术": {"引导试听": [], "促成报名": [], "应对犹豫": [], "逼单话术": []},
            "禁止回复的场景": [],
        }
        self.json_path = ""
        self.path_label.config(text="新建知识库")
        self._switch_module("基本信息")

    def _load_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.json_path = path
            self.path_label.config(text=os.path.basename(path))
            # 兼容旧版数据：确保新字段存在
            if "AI性格设定" not in self.data:
                self.data["AI性格设定"] = ""
            if "API配置" not in self.data:
                self.data["API配置"] = {"API URL": "https://open.bigmodel.cn/api/paas/v4", "API Key": "", "模型名称": "glm-4-flash"}
            self._switch_module("基本信息")
        except Exception as e:
            messagebox.showerror("加载失败", f"无法加载文件：\n{e}")

    def _save_file(self):
        if not self.json_path:
            self._save_as()
            return
        try:
            # 先把当前模块的内容写回 data（通过临时切走再切回的方式）
            self._flush_current_module()
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存成功", f"已保存到：\n{self.json_path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title="保存知识库",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
            initialfile="knowledge_base.json"
        )
        if path:
            self.json_path = path
            self._save_file()

    def _flush_current_module(self):
        """把当前编辑中的内容写回 self.data"""
        m = self.current_module
        if m == "API配置":
            self._collect_api_config()
        elif m == "基本信息":
            self._collect_basic_info()
        elif m == "产品信息":
            self._collect_products()
        elif m == "常见问题与回复":
            self._collect_faq()
        elif m == "成交话术":
            self._collect_sales()
        elif m == "禁止回复的场景":
            self._collect_rules()
        elif m == "AI性格设定":
            self._collect_personality()

    # ─────────────────── 模块切换 ───────────────────

    def _switch_module(self, module_key):
        # 先保存当前模块
        if self.current_module:
            self._flush_current_module()
        self.current_module = module_key

        for key, btn in self.nav_buttons:
            btn.config(bg="#d0e8ff" if key == module_key else "#f5f5f5",
                       font=("微软雅黑", 10, "bold") if key == module_key else ("微软雅黑", 10))

        self._clear_content()

        builders = {
            "API配置": self._build_api_config,
            "基本信息": self._build_basic_info,
            "AI性格设定": self._build_personality,
            "产品信息": self._build_products,
            "常见问题与回复": self._build_faq,
            "成交话术": self._build_sales,
            "禁止回复的场景": self._build_rules,
        }
        builders[module_key]()

        # 滚动到顶部
        self.canvas.yview_moveto(0)

    def _scroll_to_widget(self, widget):
        """滚动 canvas 使 widget 可见，并聚焦"""
        self.root.update_idletasks()
        # 用 after 延迟一帧，等布局完成
        self.root.after(50, lambda: self._do_scroll_to(widget))

    def _do_scroll_to(self, widget):
        try:
            # 找到 widget 在 canvas 中的 y 坐标
            y = self.canvas.winfo_rooty()
            wy = widget.winfo_rooty()
            delta = wy - y - 30  # 留 30px 上方间距
            if delta > 0:
                # 把 y 像素差转换为 canvas 滚动比例
                bbox = self.canvas.bbox("all")
                if bbox and bbox[3] > 0:
                    fraction = delta / (bbox[3] - self.canvas.winfo_height())
                    self.canvas.yview_moveto(min(fraction, 1.0))
            widget.focus_set()
        except Exception:
            pass

    # ═══════════════════════════════════════════════
    # 模块0：API 配置
    # ═══════════════════════════════════════════════

    def _build_api_config(self):
        f = self.scrollable_frame
        cfg = self.data.get("API配置", {})

        tk.Label(f, text="🔑 API 配置", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="配置 AI 大模型的接口信息。修改后需重启主程序才能生效。",
                 font=("微软雅黑", 9), fg="#888", wraplength=600, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        # API URL
        tk.Label(f, text="🌐 API Base URL：", font=("微软雅黑", 10, "bold"),
                 fg="#333").pack(anchor="w", padx=20, pady=(10, 3))
        self._api_url_entry = tk.Entry(f, font=("微软雅黑", 10), relief="solid", bd=1, width=70)
        self._api_url_entry.insert(0, cfg.get("API URL", "https://open.bigmodel.cn/api/paas/v4"))
        self._api_url_entry.pack(padx=20, pady=2, fill="x")

        # 预设 URL 按钮
        tk.Label(f, text="⚡ 常用 API 快速选择：", font=("微软雅黑", 9), fg="#555").pack(
            anchor="w", padx=20, pady=(8, 3))
        presets_frame = tk.Frame(f)
        presets_frame.pack(anchor="w", padx=20, pady=(0, 10))
        presets = [
            ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4"),
            ("DeepSeek", "https://api.deepseek.com/v1"),
            ("OpenAI", "https://api.openai.com/v1"),
            ("通义千问", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ("月之暗面", "https://api.moonshot.cn/v1"),
        ]
        for name, url in presets:
            tk.Button(presets_frame, text=name, font=("微软雅黑", 8), bg="#e3f2fd", fg="#1565C0",
                      relief="groove", padx=8, pady=2, cursor="hand2",
                      command=lambda u=url: (self._api_url_entry.delete(0, "end"),
                                             self._api_url_entry.insert(0, u))
                      ).pack(side="left", padx=3)

        # API Key
        tk.Label(f, text="🔐 API Key：", font=("微软雅黑", 10, "bold"),
                 fg="#333").pack(anchor="w", padx=20, pady=(10, 3))
        tk.Label(f, text="你的密钥只保存在本地 JSON 文件中，不会上传到任何服务器。",
                 font=("微软雅黑", 9), fg="#888").pack(anchor="w", padx=20, pady=(0, 3))

        key_frame = tk.Frame(f)
        key_frame.pack(padx=20, pady=2, fill="x")
        self._api_key_var = tk.StringVar(value=cfg.get("API Key", ""))
        self._api_key_entry = tk.Entry(key_frame, font=("微软雅黑", 10), relief="solid", bd=1,
                                       textvariable=self._api_key_var, show="*")
        self._api_key_entry.pack(side="left", fill="x", expand=True)
        # 显示/隐藏切换
        self._show_key_var = tk.BooleanVar(value=False)
        tk.Checkbutton(key_frame, text="显示", font=("微软雅黑", 9), variable=self._show_key_var,
                       command=lambda: self._api_key_entry.config(
                           show="" if self._show_key_var.get() else "*")
                       ).pack(side="left", padx=(8, 0))

        # 模型名称
        tk.Label(f, text="🤖 模型名称：", font=("微软雅黑", 10, "bold"),
                 fg="#333").pack(anchor="w", padx=20, pady=(10, 3))
        self._model_entry = tk.Entry(f, font=("微软雅黑", 10), relief="solid", bd=1, width=70)
        self._model_entry.insert(0, cfg.get("模型名称", "glm-4-flash"))
        self._model_entry.pack(padx=20, pady=2, fill="x")

        # 预设模型按钮
        tk.Label(f, text="⚡ 常用模型快速选择：", font=("微软雅黑", 9), fg="#555").pack(
            anchor="w", padx=20, pady=(8, 3))
        model_frame = tk.Frame(f)
        model_frame.pack(anchor="w", padx=20, pady=(0, 15))
        models = [
            ("GLM-4-Flash", "glm-4-flash"),
            ("GLM-4-Plus", "glm-4-plus"),
            ("DeepSeek-V3", "deepseek-chat"),
            ("DeepSeek-R1", "deepseek-reasoner"),
            ("GPT-4o", "gpt-4o"),
            ("GPT-4o-mini", "gpt-4o-mini"),
            ("通义千问", "qwen-turbo"),
        ]
        for name, model in models:
            tk.Button(model_frame, text=name, font=("微软雅黑", 8), bg="#e8f5e9", fg="#2E7D32",
                      relief="groove", padx=8, pady=2, cursor="hand2",
                      command=lambda m=model: (self._model_entry.delete(0, "end"),
                                              self._model_entry.insert(0, m))
                      ).pack(side="left", padx=3)

        # 测试连接按钮
        tk.Button(f, text="🔌 测试连接", font=("微软雅黑", 10), bg="#FF9800", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=self._test_api_connection).pack(anchor="w", padx=20, pady=(5, 5))

        self._api_test_result = tk.Label(f, text="", font=("微软雅黑", 9), wraplength=600, justify="left")
        self._api_test_result.pack(anchor="w", padx=20, pady=(0, 10))

    def _test_api_connection(self):
        """测试 API 连接"""
        try:
            from openai import OpenAI
            url = self._api_url_entry.get().strip()
            key = self._api_key_var.get().strip()
            model = self._model_entry.get().strip()
            if not key:
                self._api_test_result.config(text="⚠️ 请先填写 API Key", fg="#e74c3c")
                return
            if not model:
                self._api_test_result.config(text="⚠️ 请先填写模型名称", fg="#e74c3c")
                return
            self._api_test_result.config(text="⏳ 正在测试连接...", fg="#888")
            self.root.update()
            client = OpenAI(api_key=key, base_url=url)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "你好，回复OK即可"}],
                max_tokens=10,
            )
            answer = resp.choices[0].message.content.strip()
            self._api_test_result.config(
                text=f"✅ 连接成功！模型回复：{answer}", fg="#4CAF50")
            self._collect_api_config()  # 测试成功自动保存
        except Exception as e:
            self._api_test_result.config(text=f"❌ 连接失败：{e}", fg="#e74c3c")

    def _collect_api_config(self):
        self.data["API配置"] = {
            "API URL": self._api_url_entry.get().strip(),
            "API Key": self._api_key_var.get().strip(),
            "模型名称": self._model_entry.get().strip(),
        }

    # ═══════════════════════════════════════════════
    # 模块1：基本信息
    # ═══════════════════════════════════════════════

    def _build_basic_info(self):
        info = self.data.get("基本信息", {})
        f = self.scrollable_frame

        tk.Label(f, text="📋 基本信息", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="告诉 AI 你是谁、卖什么的，它才知道用什么身份回复客户",
                 font=("微软雅黑", 9), fg="#888", wraplength=600, justify="left").pack(
            anchor="w", padx=20, pady=(0, 15))

        self._basic_entries = {}
        fields = [
            ("品牌名称", "你的品牌/公司名称"),
            ("课程类型", "你卖的是什么产品/服务"),
            ("目标客户", "你的目标客户是谁"),
            ("联系方式", "客户怎么联系你（微信/手机号）"),
        ]
        for key, hint in fields:
            row = tk.Frame(f)
            row.pack(fill="x", padx=20, pady=6)
            tk.Label(row, text=key, font=("微软雅黑", 10), width=8, anchor="w").pack(side="left")
            e = tk.Entry(row, font=("微软雅黑", 10), relief="solid", bd=1)
            e.insert(0, info.get(key, ""))
            e.pack(side="left", fill="x", expand=True, padx=(10, 0))
            self._basic_entries[key] = e
            tk.Label(row, text=hint, font=("微软雅黑", 8), fg="#aaa").pack(side="right", padx=(10, 0))

        # 保存
        tk.Button(f, text="✅ 保存基本信息", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("基本信息")).pack(anchor="w", padx=20, pady=15)

    def _collect_basic_info(self):
        if "基本信息" not in self.data:
            self.data["基本信息"] = {}
        for key, entry in self._basic_entries.items():
            self.data["基本信息"][key] = entry.get().strip()

    # ═══════════════════════════════════════════════
    # 模块2：AI 性格设定（新增）
    # ═══════════════════════════════════════════════

    def _build_personality(self):
        f = self.scrollable_frame
        pers = self.data.get("AI性格设定", {})
        # 兼容旧版：如果还是字符串，转为 dict
        if isinstance(pers, str):
            pers = {"人设描述": pers, "性格规则": []}

        tk.Label(f, text="🎭 AI 性格设定", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="设定 AI 的说话风格和人设，让它回复更自然、不死板。留空则使用默认风格。",
                 font=("微软雅黑", 9), fg="#888", wraplength=600, justify="left").pack(
            anchor="w", padx=20, pady=(0, 10))

        # 快速模板
        tk.Label(f, text="⚡ 快速模板（点击自动填入描述框）：", font=("微软雅黑", 9), fg="#555").pack(
            anchor="w", padx=20, pady=(5, 3))

        templates = [
            ("知心姐姐型", '温柔亲切的知心姐姐，说话很温暖，会用语气词如"呀""呢""哦"，让人感觉像跟朋友聊天'),
            ("专业顾问型", '专业但不生硬的顾问，说话简洁有条理，偶尔幽默一下，让人觉得靠谱又有趣'),
            ("活泼幽默型", '开朗幽默的年轻人，喜欢用表情和段子，聊天氛围轻松愉快，偶尔卖萌'),
            ("沉稳可靠型", '沉稳踏实的老朋友，说话靠谱不浮夸，偶尔用成语，让人觉得可以信任'),
            ("热情销售型", '充满热情的销售达人，积极主动但不咄咄逼人，善于引导话题，感染力强'),
        ]
        tpl_frame = tk.Frame(f)
        tpl_frame.pack(anchor="w", padx=20, pady=(0, 10))
        for name, desc in templates:
            tk.Button(tpl_frame, text=name, font=("微软雅黑", 8), bg="#e3f2fd", fg="#1565C0",
                      relief="groove", padx=8, pady=2, cursor="hand2",
                      command=lambda d=desc: self._personality_text.insert("end", d)
                      ).pack(side="left", padx=3)

        # 人设描述文本框
        tk.Label(f, text="📝 人设描述（自由写 AI 的说话风格和性格）：", font=("微软雅黑", 9, "bold"),
                 fg="#333").pack(anchor="w", padx=20, pady=(5, 3))
        self._personality_text = scrolledtext.ScrolledText(
            f, width=70, height=6, font=("微软雅黑", 10), relief="solid", bd=1, wrap="word",
            spacing2=3)
        self._personality_text.insert("1.0", pers.get("人设描述", ""))
        self._personality_text.pack(padx=20, pady=5, fill="both", expand=True)

        # 提示
        tk.Label(f, text='💡 示例：你是一个温柔亲切的英语老师，说话自然不做作，偶尔用"呀""呢"等语气词，\n'
                        '像跟朋友聊天一样。不要每句话都推销课程，先关心对方的需求。',
                 font=("微软雅黑", 9), fg="#888", justify="left", wraplength=600).pack(
            anchor="w", padx=20, pady=(5, 10))

        # 分隔线
        sep = tk.Frame(f, height=1, bg="#e0e0e0")
        sep.pack(fill="x", padx=20, pady=8)

        # 性格规则列表（可增删）
        tk.Label(f, text="🏷️ 性格规则（一条条添加具体的行为规则）：", font=("微软雅黑", 9, "bold"),
                 fg="#333").pack(anchor="w", padx=20, pady=(0, 5))

        rules = pers.get("性格规则", [])
        self._personality_rules_data = list(rules)
        self._personality_rule_widgets = []
        for i, rule in enumerate(self._personality_rules_data):
            row = tk.Frame(f)
            row.pack(fill="x", padx=20, pady=2)
            e = tk.Entry(row, font=("微软雅黑", 9), relief="solid", bd=1)
            e.insert(0, rule)
            e.pack(side="left", fill="x", expand=True, padx=(0, 5))
            tk.Button(row, text="🗑", font=("微软雅黑", 9), fg="#e74c3c", relief="flat",
                      command=lambda idx=i: self._remove_personality_rule(idx)).pack(side="left")
            self._personality_rule_widgets.append(e)

        tk.Button(f, text="➕ 添加性格规则", font=("微软雅黑", 9), bg="#4CAF50", fg="white",
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  command=self._add_personality_rule).pack(anchor="w", padx=20, pady=8)

        tk.Button(f, text="✅ 保存性格设定", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("AI性格设定")).pack(anchor="w", padx=20, pady=15)

    def _add_personality_rule(self):
        self._collect_personality()
        pers = self.data.setdefault("AI性格设定", {"人设描述": "", "性格规则": []})
        if isinstance(pers, str):
            pers = {"人设描述": pers, "性格规则": []}
            self.data["AI性格设定"] = pers
        pers["性格规则"].append("")
        new_idx = len(pers["性格规则"]) - 1
        self._build_personality()
        if self._personality_rule_widgets:
            self._scroll_to_widget(self._personality_rule_widgets[new_idx])

    def _remove_personality_rule(self, idx):
        self._collect_personality()
        pers = self.data.get("AI性格设定", {})
        if isinstance(pers, dict) and "性格规则" in pers and 0 <= idx < len(pers["性格规则"]):
            pers["性格规则"].pop(idx)
        self._build_personality()

    def _collect_personality(self):
        pers = self.data.get("AI性格设定", {})
        if isinstance(pers, str):
            pers = {"人设描述": pers, "性格规则": []}
        desc = self._personality_text.get("1.0", "end").strip()
        rules = [e.get().strip() for e in self._personality_rule_widgets if e.get().strip()]
        pers["人设描述"] = desc
        pers["性格规则"] = rules
        self.data["AI性格设定"] = pers

    # ═══════════════════════════════════════════════
    # 模块3：产品信息
    # ═══════════════════════════════════════════════

    def _build_products(self):
        f = self.scrollable_frame
        products = self.data.get("产品信息", {})

        tk.Label(f, text="📦 产品/课程信息", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 10))

        # --- 课程列表 ---
        tk.Label(f, text="📚 课程/产品列表", font=("微软雅黑", 11, "bold")).pack(anchor="w", padx=20)

        courses = products.get("课程列表", [])
        self._courses_data = [dict(c) for c in courses]

        # 表头
        hdr = tk.Frame(f)
        hdr.pack(fill="x", padx=20, pady=(5, 2))
        headers = ["名称", "价格", "时长", "特色", "适合人群"]
        widths = [12, 8, 8, 25, 18]
        for h, w in zip(headers, widths):
            tk.Label(hdr, text=h, font=("微软雅黑", 9, "bold"), fg="#555", width=w, anchor="w").pack(side="left", padx=2)

        self._course_widgets = []
        for i, course in enumerate(self._courses_data):
            row_frame = tk.Frame(f)
            row_frame.pack(fill="x", padx=20, pady=2)
            entries = []
            for j, (key, w) in enumerate(zip(headers, widths)):
                e = tk.Entry(row_frame, width=w, font=("微软雅黑", 9), relief="solid", bd=1)
                e.insert(0, course.get(key, ""))
                e.pack(side="left", padx=2)
                entries.append((key, e))
            tk.Button(row_frame, text="🗑", font=("微软雅黑", 9), fg="#e74c3c", relief="flat",
                      command=lambda idx=i: self._remove_course(idx)).pack(side="left", padx=4)
            self._course_widgets.append((row_frame, entries))

        tk.Button(f, text="➕ 添加课程", font=("微软雅黑", 9), bg="#4CAF50", fg="white",
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  command=self._add_course).pack(anchor="w", padx=20, pady=8)

        # --- 课程优势 ---
        sep = tk.Frame(f, height=1, bg="#e0e0e0")
        sep.pack(fill="x", padx=20, pady=10)

        tk.Label(f, text="🌟 产品/课程优势", font=("微软雅黑", 11, "bold")).pack(anchor="w", padx=20)

        self._advantages_data = list(products.get("课程优势", []))
        self._advantage_widgets = []
        for i, adv in enumerate(self._advantages_data):
            row = tk.Frame(f)
            row.pack(fill="x", padx=20, pady=2)
            e = tk.Entry(row, font=("微软雅黑", 9), relief="solid", bd=1)
            e.insert(0, adv)
            e.pack(side="left", fill="x", expand=True, padx=(0, 5))
            tk.Button(row, text="🗑", font=("微软雅黑", 9), fg="#e74c3c", relief="flat",
                      command=lambda idx=i: self._remove_advantage(idx)).pack(side="left")
            self._advantage_widgets.append((row, e))

        tk.Button(f, text="➕ 添加优势", font=("微软雅黑", 9), bg="#4CAF50", fg="white",
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  command=self._add_advantage).pack(anchor="w", padx=20, pady=8)

        tk.Button(f, text="✅ 保存产品信息", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("产品信息")).pack(anchor="w", padx=20, pady=15)

    def _add_course(self):
        """先收集当前数据，添加空行，然后重绘并滚动到新行"""
        self._collect_products()
        self._courses_data.append({"名称": "", "价格": "", "时长": "", "特色": "", "适合人群": ""})
        new_idx = len(self._courses_data) - 1
        self._build_products()
        if self._course_widgets:
            row_frame, entries = self._course_widgets[new_idx]
            first_entry = entries[0][1]  # 第一个 Entry（名称）
            self._scroll_to_widget(first_entry)

    def _remove_course(self, idx):
        self._collect_products()
        self._courses_data.pop(idx)
        self._build_products()

    def _add_advantage(self):
        self._collect_products()
        self._advantages_data.append("")
        new_idx = len(self._advantages_data) - 1
        self._build_products()
        if self._advantage_widgets:
            _, e = self._advantage_widgets[new_idx]
            self._scroll_to_widget(e)

    def _remove_advantage(self, idx):
        self._collect_products()
        self._advantages_data.pop(idx)
        self._build_products()

    def _collect_products(self):
        courses = []
        for _, entries in self._course_widgets:
            course = {}
            for key, e in entries:
                course[key] = e.get().strip()
            if any(course.values()):
                courses.append(course)
        advantages = [e.get().strip() for _, e in self._advantage_widgets if e.get().strip()]
        if "产品信息" not in self.data:
            self.data["产品信息"] = {}
        self.data["产品信息"]["课程列表"] = courses
        self.data["产品信息"]["课程优势"] = advantages
        # 同步回工作数据
        self._courses_data = courses
        self._advantages_data = advantages

    # ═══════════════════════════════════════════════
    # 模块4：常见问题
    # ═══════════════════════════════════════════════

    def _build_faq(self):
        f = self.scrollable_frame
        faqs = self.data.get("常见问题与回复", [])

        tk.Label(f, text="❓ 常见问题与回复", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="设置关键词 → AI 看到这些词就会参考你写的回复来回答客户",
                 font=("微软雅黑", 9), fg="#888").pack(anchor="w", padx=20, pady=(0, 10))

        self._faq_widgets = []
        for i, faq in enumerate(faqs):
            self._add_faq_block(i, faq)

        tk.Button(f, text="➕ 添加问答", font=("微软雅黑", 10), bg="#4CAF50", fg="white",
                  relief="flat", padx=15, pady=5, cursor="hand2",
                  command=self._add_faq_empty).pack(anchor="w", padx=20, pady=10)

        tk.Button(f, text="✅ 保存常见问题", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("常见问题与回复")).pack(anchor="w", padx=20, pady=15)

    def _add_faq_block(self, idx, faq=None):
        f = self.scrollable_frame

        # 卡片边框
        card = tk.Frame(f, bd=1, relief="groove", padx=10, pady=8)
        card.pack(fill="x", padx=20, pady=4)

        # 头部：序号 + 删除
        header = tk.Frame(card)
        header.pack(fill="x")
        tk.Label(header, text=f"第 {idx + 1} 条", font=("微软雅黑", 9, "bold"), fg="#555").pack(side="left")
        tk.Button(header, text="🗑 删除", font=("微软雅黑", 8), fg="#e74c3c", relief="flat",
                  command=lambda: self._remove_faq(idx)).pack(side="right")

        # 关键词行
        kw_row = tk.Frame(card)
        kw_row.pack(fill="x", pady=(5, 2))
        tk.Label(kw_row, text="🔑 关键词：", font=("微软雅黑", 9)).pack(side="left")
        kw_entry = tk.Entry(kw_row, font=("微软雅黑", 9), relief="solid", bd=1)
        kw_str = "、".join(faq.get("关键词", [])) if faq else ""
        kw_entry.insert(0, kw_str)
        kw_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        tk.Label(kw_row, text="（用顿号分隔）", font=("微软雅黑", 8), fg="#aaa").pack(side="right", padx=(5, 0))

        # 回复行
        reply_row = tk.Frame(card)
        reply_row.pack(fill="x", pady=(3, 0))
        tk.Label(reply_row, text="💬 回复：", font=("微软雅黑", 9)).pack(side="left", anchor="n")
        reply_text = scrolledtext.ScrolledText(reply_row, height=2, font=("微软雅黑", 9),
                                               relief="solid", bd=1, wrap="word")
        reply_text.insert("1.0", faq.get("回复", "") if faq else "")
        reply_text.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self._faq_widgets.append((kw_entry, reply_text))

    def _add_faq_empty(self):
        self._collect_faq()
        self.data["常见问题与回复"].append({"关键词": [], "回复": ""})
        new_idx = len(self.data["常见问题与回复"]) - 1
        self._build_faq()
        if self._faq_widgets:
            kw_entry, _ = self._faq_widgets[new_idx]
            self._scroll_to_widget(kw_entry)

    def _remove_faq(self, idx):
        self._collect_faq()
        if 0 <= idx < len(self.data["常见问题与回复"]):
            self.data["常见问题与回复"].pop(idx)
        self._build_faq()

    def _collect_faq(self):
        faqs = []
        for kw_entry, reply_text in self._faq_widgets:
            keywords = [k.strip() for k in kw_entry.get().strip().split("、") if k.strip()]
            reply = reply_text.get("1.0", "end").strip()
            faqs.append({"关键词": keywords, "回复": reply})
        self.data["常见问题与回复"] = faqs

    # ═══════════════════════════════════════════════
    # 模块5：成交话术
    # ═══════════════════════════════════════════════

    def _build_sales(self):
        f = self.scrollable_frame
        sales = self.data.get("成交话术", {})

        tk.Label(f, text="💬 成交话术", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="给 AI 准备不同阶段的参考话术，让回复更专业",
                 font=("微软雅黑", 9), fg="#888").pack(anchor="w", padx=20, pady=(0, 10))

        stages = ["引导试听", "促成报名", "应对犹豫", "逼单话术"]
        self._sales_widgets = {}

        for stage in stages:
            lines = sales.get(stage, [])

            stage_card = tk.Frame(f, bd=1, relief="groove", padx=10, pady=8)
            stage_card.pack(fill="x", padx=20, pady=4)

            tk.Label(stage_card, text=f"📌 {stage}", font=("微软雅黑", 10, "bold")).pack(anchor="w")

            entries = []
            for i, line in enumerate(lines):
                row = tk.Frame(stage_card)
                row.pack(fill="x", pady=1)
                e = tk.Entry(row, font=("微软雅黑", 9), relief="solid", bd=1)
                e.insert(0, line)
                e.pack(side="left", fill="x", expand=True, padx=(10, 5))
                tk.Button(row, text="🗑", font=("微软雅黑", 8), fg="#e74c3c", relief="flat",
                          command=lambda s=stage, idx=i: self._remove_sales_line(s, idx)).pack(side="left")
                entries.append(e)

            tk.Button(stage_card, text=f"➕ 添加话术", font=("微软雅黑", 8), bg="#e8f5e9", fg="#333",
                      relief="flat", padx=8, pady=1, cursor="hand2",
                      command=lambda s=stage: self._add_sales_line(s)).pack(anchor="w", padx=(10, 0), pady=3)

            self._sales_widgets[stage] = entries

        tk.Button(f, text="✅ 保存成交话术", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("成交话术")).pack(anchor="w", padx=20, pady=15)

    def _add_sales_line(self, stage):
        self._collect_sales()
        if stage not in self.data["成交话术"]:
            self.data["成交话术"][stage] = []
        self.data["成交话术"][stage].append("")
        new_idx = len(self.data["成交话术"][stage]) - 1
        self._build_sales()
        if stage in self._sales_widgets and self._sales_widgets[stage]:
            e = self._sales_widgets[stage][new_idx]
            self._scroll_to_widget(e)

    def _remove_sales_line(self, stage, idx):
        self._collect_sales()
        if stage in self.data["成交话术"] and 0 <= idx < len(self.data["成交话术"][stage]):
            self.data["成交话术"][stage].pop(idx)
        self._build_sales()

    def _collect_sales(self):
        if "成交话术" not in self.data:
            self.data["成交话术"] = {}
        for stage, entries in self._sales_widgets.items():
            self.data["成交话术"][stage] = [e.get().strip() for e in entries]

    # ═══════════════════════════════════════════════
    # 模块6：注意事项
    # ═══════════════════════════════════════════════

    def _build_rules(self):
        f = self.scrollable_frame
        rules = self.data.get("禁止回复的场景", [])

        tk.Label(f, text="⚠️ 注意事项 / 禁止场景", font=("微软雅黑", 14, "bold")).pack(
            anchor="w", padx=20, pady=(15, 5))
        tk.Label(f, text="告诉 AI 哪些情况不要回复或要注意什么",
                 font=("微软雅黑", 9), fg="#888").pack(anchor="w", padx=20, pady=(0, 10))

        self._rule_widgets = []
        for i, rule in enumerate(rules):
            row = tk.Frame(f)
            row.pack(fill="x", padx=20, pady=2)
            e = tk.Entry(row, font=("微软雅黑", 9), relief="solid", bd=1)
            e.insert(0, rule)
            e.pack(side="left", fill="x", expand=True, padx=(0, 5))
            tk.Button(row, text="🗑", font=("微软雅黑", 9), fg="#e74c3c", relief="flat",
                      command=lambda idx=i: self._remove_rule(idx)).pack(side="left")
            self._rule_widgets.append(e)

        tk.Button(f, text="➕ 添加规则", font=("微软雅黑", 10), bg="#4CAF50", fg="white",
                  relief="flat", padx=15, pady=5, cursor="hand2",
                  command=self._add_rule).pack(anchor="w", padx=20, pady=10)

        tk.Button(f, text="✅ 保存注意事项", font=("微软雅黑", 10), bg="#2196F3", fg="white",
                  relief="flat", padx=20, pady=6, cursor="hand2",
                  command=lambda: self._do_save("禁止回复的场景")).pack(anchor="w", padx=20, pady=15)

    def _add_rule(self):
        self._collect_rules()
        self.data["禁止回复的场景"].append("")
        new_idx = len(self.data["禁止回复的场景"]) - 1
        self._build_rules()
        if self._rule_widgets:
            e = self._rule_widgets[new_idx]
            self._scroll_to_widget(e)

    def _remove_rule(self, idx):
        self._collect_rules()
        if 0 <= idx < len(self.data["禁止回复的场景"]):
            self.data["禁止回复的场景"].pop(idx)
        self._build_rules()

    def _collect_rules(self):
        self.data["禁止回复的场景"] = [e.get().strip() for e in self._rule_widgets if e.get().strip()]

    # ═══════════════════════════════════════════════
    # 通用保存
    # ═══════════════════════════════════════════════

    def _do_save(self, module_name):
        """保存当前模块并弹确认"""
        labels = {
            "基本信息": "基本信息",
            "AI性格设定": "性格设定",
            "产品信息": "产品信息",
            "常见问题与回复": "常见问题",
            "成交话术": "成交话术",
            "禁止回复的场景": "注意事项",
        }
        messagebox.showinfo("已保存", f"{labels.get(module_name, module_name)}已更新！\n\n"
                                     f"记得点顶部「💾 保存到文件」写入磁盘。")

    # ─────────────────── 运行 ───────────────────

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = KnowledgeEditor()
    app.run()
