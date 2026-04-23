import pyautogui
import pyperclip
import ctypes
from PIL import Image
import easyocr
import sys
import os
import json
import cv2
import numpy as np
import time
import ssl
import tkinter as tk
import threading
import traceback
import logging
from openai import OpenAI

# windowed 模式下 stdout/stderr 可能是 None
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# ======== 日志配置 ========
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "wechat_bot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w"),
    ]
)
log = logging.getLogger("wechat_bot")

ssl._create_default_https_context = ssl._create_unverified_context

# ======== 全局 AI 客户端（启动时从知识库读取配置） ========
client = None  # 由 init_ai_client() 初始化
AI_MODEL = "glm-4-flash"  # 默认值，由 init_ai_client() 覆盖


def init_ai_client(kb):
    """从知识库的 API配置 初始化 OpenAI 客户端"""
    global client, AI_MODEL
    cfg = kb.get("API配置", {}) if kb else {}
    api_url = cfg.get("API URL", "https://open.bigmodel.cn/api/paas/v4")
    api_key = cfg.get("API Key", "YOUR_API_KEY_HERE")
    AI_MODEL = cfg.get("模型名称", "glm-4-flash")
    client = OpenAI(api_key=api_key, base_url=api_url)
    log.info(f"AI 客户端已初始化: url={api_url}, model={AI_MODEL}")


# ======== Tkinter 提示窗口（独立线程） ========
class TipWindow:
    """小型悬浮提示窗口，在独立线程中运行 mainloop"""
    def __init__(self):
        self.text_var = None
        self.root = None
        self._thread = None
        self._ready = threading.Event()
        self.should_exit = False  # 主循环检测此标志

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        log.info("TipWindow 线程已启动")

    def _run(self):
        try:
            self.root = tk.Tk()
            self.root.title("微信AI自动回复")
            self.root.attributes("-topmost", True)
            # 不用 overrideredirect，保留标题栏，避免鼠标经过时窗口消失
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry("420x48+{}+{}".format(sw - 440, sh - 90))
            self.root.configure(bg="#1a1a2e")
            self.root.resizable(False, False)

            # 左侧：状态文字
            frame = tk.Frame(self.root, bg="#1a1a2e")
            frame.pack(fill="both", expand=True)

            self.text_var = tk.StringVar(value="初始化中...")
            self.label = tk.Label(
                frame, textvariable=self.text_var,
                font=("微软雅黑", 10), fg="#00ff88", bg="#1a1a2e",
                anchor="w", padx=10
            )
            self.label.pack(side="left", fill="y")

            # 右侧：退出按钮
            quit_btn = tk.Button(
                frame, text=" 退出 ", font=("微软雅黑", 9),
                fg="#ffffff", bg="#e74c3c", activebackground="#c0392b",
                activeforeground="#ffffff", relief="flat", bd=0,
                cursor="hand2", command=self._close
            )
            quit_btn.pack(side="right", padx=8, pady=10)

            self._ready.set()
            self.root.mainloop()
            log.info("Tkinter mainloop 已退出")
        except Exception as e:
            log.error(f"TipWindow 创建失败: {e}")
            traceback.print_exc()
            self._ready.set()

    def update(self, text):
        try:
            if self.text_var:
                self.text_var.set(text)
        except:
            pass

    def _close(self):
        self.should_exit = True
        try:
            if self.root and self.root.winfo_exists():
                self.root.destroy()
        except:
            pass

    def close(self):
        self._close()

    def is_alive(self):
        try:
            return self.root is not None and self.root.winfo_exists()
        except:
            return False


# ======== 确保微信在前台 ========
def bring_wechat_front(tip_win):
    """尝试用任务栏点击方式把微信带到前台"""
    try:
        # 方法1: 用 pyautogui 的方式模拟 Alt+Tab 太不可控，改用点击任务栏
        # 方法2: 直接用 Windows API 找微信窗口并前置
        import ctypes.wintypes

        FindWindow = ctypes.windll.user32.FindWindowW
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
        ShowWindow = ctypes.windll.user32.ShowWindow
        IsIconic = ctypes.windll.user32.IsIconic

        # 微信窗口类名
        hwnd = FindWindow("WeChatMainWndForPC", None)
        if hwnd:
            if IsIconic(hwnd):
                ShowWindow(hwnd, 9)  # SW_RESTORE
            SetForegroundWindow(hwnd)
            time.sleep(0.3)
            log.info("微信窗口已前置")
            return True
        else:
            log.warning("未找到微信窗口句柄")
    except Exception as e:
        log.error(f"bring_wechat_front 异常: {e}")
    return False


# ======== 安全点击（不使用 ESC） ========
def safe_back_to_list(contact_x, contact_y, tip_win):
    """通过点击联系人区域返回消息列表，不用 ESC"""
    try:
        tip_win.update("  返回消息列表...")
        # 点联系人列表区域（非当前聊天区域）来返回
        # 先点一下列表区域的中上部（通常是聊天列表）
        list_click_x = contact_x
        list_click_y = contact_y - 30  # 稍微往上点
        pyautogui.click(list_click_x, list_click_y)
        time.sleep(0.5)
        log.info("安全返回列表")
    except Exception as e:
        log.error(f"safe_back_to_list 异常: {e}")


# ======== 知识库与系统提示 ========
def load_knowledge_base():
    possible_paths = [
        os.path.join(sys._MEIPASS, "knowledge_base.json") if hasattr(sys, '_MEIPASS') else "",
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "knowledge_base.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.json"),
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                kb = json.load(f)
            log.info(f"知识库已加载: {path}")
            return kb
    log.warning("未找到 knowledge_base.json，使用通用回复")
    return None


def build_system_prompt(kb):
    if not kb:
        return ("你是微信聊天助手。用简短自然的一句话回复，像真人聊天一样。"
                "用户发来的文字可能因为OCR识别有一些错别字，请根据上下文理解意思。")

    parts = []
    info = kb.get("基本信息", {})
    brand = info.get("品牌名称", "英语培训")
    target = info.get("目标客户", "英语学习者")
    parts.append(f"你是「{brand}」的课程顾问，负责在微信上和客户聊天，目标是推荐合适的英语课程并促成成交。目标客户群体：{target}。")

    # AI 性格设定
    personality = kb.get("AI性格设定", "")
    if personality and isinstance(personality, str) and personality.strip():
        parts.append(f"\n【你的性格与人设】\n{personality.strip()}")
    elif personality and isinstance(personality, dict):
        pers_parts = []
        desc = personality.get("人设描述", "")
        if desc and desc.strip():
            pers_parts.append(desc.strip())
        rules = personality.get("性格规则", [])
        if rules:
            pers_parts.append("\n".join([f"- {r}" for r in rules if r.strip()]))
        if pers_parts:
            parts.append(f"\n【你的性格与人设】\n" + "\n".join(pers_parts))

    products = kb.get("产品信息", {})
    courses = products.get("课程列表", [])
    advantages = products.get("课程优势", [])
    course_text = "\n".join(
        [f"- {c['名称']}: {c.get('价格','')}, {c.get('时长','')}, {c.get('特色','')}, 适合{c.get('适合人群','')}"
         for c in courses]
    )
    if course_text:
        parts.append(f"\n【课程信息】\n{course_text}")
    if advantages:
        parts.append(f"\n【课程优势】\n" + "\n".join([f"- {a}" for a in advantages]))

    faqs = kb.get("常见问题与回复", [])
    faq_text = "\n".join(
        [f"- 客户提到{'/'.join(q['关键词'])}时参考回复：{q['回复']}" for q in faqs]
    )
    if faq_text:
        parts.append(f"\n【常见问题参考回复】\n{faq_text}")

    sales = kb.get("成交话术", {})
    sales_parts = []
    for stage, lines in sales.items():
        sales_parts.append(f"{stage}：" + "；".join(lines))
    if sales_parts:
        parts.append("\n【成交话术参考】\n" + "\n".join(sales_parts))

    rules = kb.get("禁止回复的场景", [])
    if rules:
        parts.append("\n【注意事项】\n" + "\n".join([f"- {r}" for r in rules]))

    parts.append(
        "\n【回复要求】"
        "\n1. 用简短自然的语气回复，像真人微信聊天，不要像客服机器人"
        "\n2. 根据客户问题匹配知识库中的信息来回答"
        "\n3. 用户发来的文字可能因为OCR识别有一些错别字，请根据上下文理解意思"
        "\n4. 每次回复控制在1-3句话，不要太长"
        "\n5. 适时引导客户试听或报名，但不要每句话都推销"
        "\n6. 如果客户表现出兴趣，主动推进成交"
    )
    return "\n".join(parts)


# ======== 坐标捕获 ========
def capture_clicks(total_clicks, tip_win):
    """纯轮询方式捕获鼠标点击坐标，用 Windows API 检测鼠标左键"""
    clicks = []
    prompts = [
        "① 请点击 红点监控区域 左上角",
        "② 请点击 红点监控区域 右下角",
        "③ 请点击 目标联系人位置",
        "④ 请点击 聊天区域 左上角",
        "⑤ 请点击 聊天区域 右下角",
        "⑥ 请点击 聊天输入框位置",
    ]

    for i in range(total_clicks):
        prompt = prompts[i] if i < len(prompts) else f"请点击位置 {i+1}"
        tip_win.update(f"  {prompt}  ({i+1}/{total_clicks})")

        captured = False
        time.sleep(0.4)

        while not captured:
            time.sleep(0.05)
            try:
                state = ctypes.windll.user32.GetAsyncKeyState(0x01)
                if state & 0x8000:
                    while ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                        time.sleep(0.02)
                    x, y = pyautogui.position()
                    x, y = int(x), int(y)
                    clicks.append((x, y))
                    log.info(f"捕获坐标 ({i+1}/{total_clicks}): ({x}, {y})")
                    tip_win.update(f"  OK ({x}, {y})  ({i+1}/{total_clicks})")
                    captured = True
                    time.sleep(0.3)
            except Exception as e:
                log.error(f"capture_clicks 异常: {e}")
                time.sleep(0.1)

    return clicks


# ======== 红点检测 ========
def detect_red_dot(screenshot, min_area=15):
    try:
        img = np.array(screenshot)
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = mask1 | mask2
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            ar = float(w) / max(h, 1)
            if 0.5 <= ar <= 2.0 and w < 40 and h < 40:
                return True, x + w // 2, y + h // 2
    except Exception as e:
        log.error(f"detect_red_dot 异常: {e}")
    return False, 0, 0


# ======== 截图 ========
def screenshot_region(left, top, width, height):
    try:
        pil_img = pyautogui.screenshot(region=(left, top, width, height))
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        log.error(f"screenshot_region 异常: {e}")
        return None


# ======== 像素变化检测 ========
def has_pixel_changed(base_bgr, current_bgr, threshold=30, min_pixel_count=30):
    try:
        diff = cv2.absdiff(base_bgr, current_bgr)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, threshold, 255, cv2.THRESH_BINARY)

        changed_pixels = np.count_nonzero(thresh)
        if changed_pixels < min_pixel_count:
            return False, []

        kernel = np.ones((3, 9), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_DILATE, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 80:
                continue
            x, y, w, h = cv2.boundingRect(c)
            boxes.append((x, y, w, h))

        return True, boxes
    except Exception as e:
        log.error(f"has_pixel_changed 异常: {e}")
        return False, []


# ======== 气泡颜色判断 ========
def is_boxes_green_bubble(current_bgr, boxes):
    try:
        if not boxes:
            return 'unknown'

        hsv = cv2.cvtColor(current_bgr, cv2.COLOR_BGR2HSV)
        green_count = 0
        white_count = 0

        for (x, y, w, h) in boxes:
            margin = max(3, min(w, h) // 6)
            sx = max(0, x + margin)
            sy = max(0, y + margin)
            ex = min(current_bgr.shape[1], x + w - margin)
            ey = min(current_bgr.shape[0], y + h - margin)

            if ex <= sx or ey <= sy:
                continue

            roi = hsv[sy:ey, sx:ex]

            green_mask = cv2.inRange(roi, np.array([35, 40, 120]), np.array([85, 255, 255]))
            green_ratio = np.count_nonzero(green_mask) / max(roi.shape[0] * roi.shape[1], 1)

            white_mask = cv2.inRange(roi, np.array([0, 0, 200]), np.array([180, 30, 255]))
            white_ratio = np.count_nonzero(white_mask) / max(roi.shape[0] * roi.shape[1], 1)

            if green_ratio > 0.15:
                green_count += 1
            elif white_ratio > 0.3:
                white_count += 1

        total = green_count + white_count
        if total == 0:
            return 'unknown'
        if green_count > white_count:
            return 'self'
        elif white_count > green_count:
            return 'other'
    except Exception as e:
        log.error(f"is_boxes_green_bubble 异常: {e}")
    return 'unknown'


# ======== 噪音过滤 ========
def is_tech_noise(text):
    tech_keywords = [
        'torch', 'pin_memory', 'dataloader', 'accelerator', 'super()',
        'UserWarning', 'WARNING', 'Traceback', 'Error', 'CUDA', 'MPS',
        'import ', 'def ', 'class ', 'print(', 'return ',
    ]
    text_lower = text.lower()
    for kw in tech_keywords:
        if kw.lower() in text_lower:
            return True
    code_chars = sum(1 for c in text if c.isascii() and (c.isalpha() or c in '_.:/\\()[]{}'))
    if len(text.strip()) > 0 and code_chars / len(text.strip()) > 0.5:
        return True
    return False


def is_self_message_by_color(bgr_img, bbox):
    """通过 OCR 文字块上方的气泡颜色判断是否是自己（绿色）的消息。
    bbox 是 easyocr 返回的 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] 格式。
    微信气泡文字上方一小段就是气泡背景色，采样该区域判断。"""
    try:
        hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
        h = bgr_img.shape[0]
        # 取文字框上方区域（气泡背景）
        x1 = int(bbox[0][0])
        y1 = int(bbox[0][1])
        x2 = int(bbox[2][0])
        y2 = int(bbox[2][1])
        # 上方 8-20 像素区域
        sample_top = max(0, y1 - 18)
        sample_bottom = max(0, y1 - 4)
        sample_left = max(0, x1 - 2)
        sample_right = min(bgr_img.shape[1], x2 + 2)

        if sample_bottom <= sample_top or sample_right <= sample_left:
            return False

        roi = hsv[sample_top:sample_bottom, sample_left:sample_right]
        if roi.size == 0:
            return False

        # 微信自己消息的绿色气泡 HSV 范围
        green_mask = cv2.inRange(roi, np.array([35, 40, 100]), np.array([85, 255, 255]))
        green_ratio = np.count_nonzero(green_mask) / max(roi.shape[0] * roi.shape[1], 1)

        if green_ratio > 0.2:
            return True

        # 微信对方消息的白色气泡 HSV 范围
        white_mask = cv2.inRange(roi, np.array([0, 0, 200]), np.array([180, 30, 255]))
        white_ratio = np.count_nonzero(white_mask) / max(roi.shape[0] * roi.shape[1], 1)
        if white_ratio > 0.3:
            return False

        # 都不是，位置判断兜底：右侧 = 自己
        cx = (x1 + x2) / 2
        return cx > bgr_img.shape[1] * 0.55
    except:
        return False


# ======== OCR ========
def do_ocr(reader, bgr_img):
    try:
        gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return reader.readtext(enhanced)
    except Exception as e:
        log.error(f"do_ocr 异常: {e}")
        traceback.print_exc()
        return []


# ======== AI 回复 ========
def do_reply(msg, system_prompt, input_x, input_y, tip_win):
    if not msg or len(msg.strip()) < 1:
        return ""
    try:
        tip_win.update("  AI 思考中...")
        log.info(f"AI 回复中，消息: {msg[:30]}...")
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg},
            ],
            stream=False
        )
        response_msg = response.choices[0].message.content
        log.info(f"AI 回复: {response_msg[:50]}...")

        # 先确保输入框获取焦点
        pyautogui.click(input_x, input_y)
        time.sleep(0.3)

        # 用 pyperclip + ctrl+v 粘贴
        pyperclip.copy(response_msg)
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        # 按 enter 发送
        pyautogui.press('enter')
        time.sleep(0.3)
        return response_msg
    except Exception as e:
        log.error(f"do_reply 异常: {e}")
        traceback.print_exc()
        return ""


# ======== 主函数 ========
def main():
    tip = TipWindow()
    tip.update("  微信AI自动回复 v6")

    try:
        kb = load_knowledge_base()
        init_ai_client(kb)
        system_prompt = build_system_prompt(kb)

        # ======== 阶段1：捕获坐标 ========
        tip.update("  请依次点击 6 个位置校准...")

        clicks = capture_clicks(total_clicks=6, tip_win=tip)

        if len(clicks) < 6:
            tip.update("  错误：需要 6 个点！")
            time.sleep(3)
            tip.close()
            return

        rx1, ry1 = clicks[0]
        rx2, ry2 = clicks[1]
        contact_x, contact_y = clicks[2]
        cx1, cy1 = clicks[3]
        cx2, cy2 = clicks[4]
        input_x, input_y = clicks[5]

        red_left = min(rx1, rx2)
        red_top = min(ry1, ry2)
        red_width = abs(rx1 - rx2)
        red_height = abs(ry1 - ry2)

        chat_left = min(cx1, cx2)
        chat_top = min(cy1, cy2)
        chat_width = abs(cx1 - cx2)
        chat_height = abs(cy1 - cy2)

        log.info(f"红点区域: ({red_left},{red_top}) {red_width}x{red_height}")
        log.info(f"联系人: ({contact_x},{contact_y})")
        log.info(f"聊天区域: ({chat_left},{chat_top}) {chat_width}x{chat_height}")
        log.info(f"输入框: ({input_x},{input_y})")

        # ======== 阶段2：初始化 OCR ========
        tip.update("  正在加载 OCR 模型（首次较慢）...")
        reader = easyocr.Reader(['ch_sim', 'en'])
        log.info("OCR 模型加载完成")
        tip.update("  OCR 就绪，监控红点中...  右键退出")

        # ======== 阶段3：主循环 ========
        base_bgr = None
        cooldown_until = 0
        COOLDOWN = 8
        POLL = 2
        TIMEOUT = 30
        in_chat = False
        enter_time = 0
        replied_ids = set()

        while True:
            try:
                if tip.should_exit or not tip.is_alive():
                    log.info("用户点击退出，程序结束")
                    break

                now = time.time()
                if now < cooldown_until:
                    time.sleep(1)
                    continue

                # ========== 状态A：在消息列表 ==========
                if not in_chat:
                    tip.update("  监控红点中...")

                    try:
                        red_img = pyautogui.screenshot(region=(red_left, red_top, red_width, red_height))
                        found, _, _ = detect_red_dot(red_img)
                    except Exception as e:
                        log.error(f"红点检测截图失败: {e}")
                        time.sleep(POLL)
                        continue

                    if found:
                        log.info("检测到红点，进入聊天")
                        tip.update("  检测到红点，进入聊天...")

                        # 确保微信在前台
                        bring_wechat_front(tip)
                        time.sleep(0.3)

                        try:
                            pyautogui.click(contact_x, contact_y)
                            time.sleep(2)
                            in_chat = True
                            enter_time = time.time()

                            # 进入聊天后直接 OCR 当前画面（不依赖像素变化）
                            current_bgr = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                            if current_bgr is not None:
                                log.info("进入聊天，直接OCR首屏")
                                tip.update("  读取消息中...")
                                results = do_ocr(reader, current_bgr)
                                msg_parts = []
                                for r in results:
                                    bbox, text, conf = r[0], r[1], r[2]
                                    if text in replied_ids or is_tech_noise(text):
                                        continue
                                    # 通过气泡颜色判断是否自己的消息
                                    if is_self_message_by_color(current_bgr, bbox):
                                        log.info(f"跳过自己的消息(颜色): {text[:20]}")
                                        replied_ids.add(text)
                                        continue
                                    msg_parts.append(text)
                                if msg_parts:
                                    msg = "".join(msg_parts)
                                    log.info(f"首屏对方消息: {msg[:50]}")
                                    do_reply(msg, system_prompt, input_x, input_y, tip)
                                    for t in msg_parts:
                                        replied_ids.add(t)
                                    cooldown_until = time.time() + COOLDOWN
                                else:
                                    log.info("首屏无对方消息")
                            else:
                                log.warning("首屏截图失败")

                            # 用当前画面作为后续对比基准
                            time.sleep(1)
                            base_bgr = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                            tip.update("  等待新消息...")
                        except Exception as e:
                            log.error(f"进入聊天处理异常: {e}")
                            traceback.print_exc()
                            in_chat = False
                            base_bgr = None
                            replied_ids = set()
                    time.sleep(POLL)

                # ========== 状态B：在聊天界面 ==========
                else:
                    try:
                        current_bgr = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                        if current_bgr is None or base_bgr is None:
                            time.sleep(POLL)
                            continue

                        changed, boxes = has_pixel_changed(base_bgr, current_bgr)
                    except Exception as e:
                        log.error(f"截图/对比失败: {e}")
                        time.sleep(POLL)
                        continue

                    if changed and boxes:
                        who = is_boxes_green_bubble(current_bgr, boxes)

                        if who == 'other':
                            log.info("检测到对方新消息")
                            tip.update("  对方新消息，处理中...")
                            try:
                                results = do_ocr(reader, current_bgr)
                                msg_parts = []
                                for r in results:
                                    bbox, text, conf = r[0], r[1], r[2]
                                    if text in replied_ids or is_tech_noise(text):
                                        continue
                                    if is_self_message_by_color(current_bgr, bbox):
                                        log.info(f"跳过自己的消息(颜色): {text[:20]}")
                                        replied_ids.add(text)
                                        continue
                                    msg_parts.append(text)

                                if msg_parts:
                                    msg = "".join(msg_parts)
                                    log.info(f"消息内容: {msg[:30]}...")
                                    do_reply(msg, system_prompt, input_x, input_y, tip)
                                    for t in msg_parts:
                                        replied_ids.add(t)
                                else:
                                    log.info("OCR 无有效文字（可能是图片/表情包）")
                            except Exception as e:
                                log.error(f"OCR/回复处理异常: {e}")
                                traceback.print_exc()

                            cooldown_until = time.time() + COOLDOWN
                            time.sleep(3)
                            new_base = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                            if new_base is not None:
                                base_bgr = new_base
                            enter_time = time.time()
                            tip.update("  等待新消息...")

                        elif who == 'self':
                            log.info("跳过自己的消息")
                            tip.update("  跳过（自己的消息）")
                            cooldown_until = time.time() + 3
                            time.sleep(3)
                            new_base = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                            if new_base is not None:
                                base_bgr = new_base
                            enter_time = time.time()
                            tip.update("  等待新消息...")

                        else:
                            cooldown_until = time.time() + 3
                            time.sleep(2)
                            new_base = screenshot_region(chat_left, chat_top, chat_width, chat_height)
                            if new_base is not None:
                                base_bgr = new_base
                            enter_time = time.time()

                    elif not changed:
                        if now - enter_time > TIMEOUT:
                            log.info(f"超时 {TIMEOUT}s，返回列表")
                            tip.update("  超时，返回列表...")
                            safe_back_to_list(contact_x, contact_y, tip)
                            in_chat = False
                            base_bgr = None
                            replied_ids = set()
                            time.sleep(1)

                    time.sleep(POLL)

            except Exception as e:
                log.error(f"主循环异常: {e}")
                traceback.print_exc()
                in_chat = False
                base_bgr = None
                replied_ids = set()
                try:
                    tip.update("  异常恢复中，继续监控...")
                except:
                    pass
                time.sleep(3)

    except Exception as e:
        log.error(f"程序严重异常: {e}")
        traceback.print_exc()
        # 异常时窗口显示错误，等 5 秒让用户看到
        try:
            tip.update("  发生错误，请查看日志")
            time.sleep(5)
        except:
            pass
    finally:
        tip.close()


if __name__ == "__main__":
    main()
