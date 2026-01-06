import customtkinter as ctk
import threading
import subprocess
import os
import time
import datetime
import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==========================================
# PHẦN 1: ADB HELPER (Xử lý kết nối & Chụp)
# ==========================================
class ADBHelper:
    def __init__(self, device_id):
        self.device_id = device_id
        self.adb_path = "adb"  # Đảm bảo bạn đã cài ADB vào biến môi trường

    def capture_screen(self):
        """Chụp màn hình và trả về OpenCV Image (numpy array)"""
        try:
            pipe = subprocess.Popen(
                f'{self.adb_path} -s {self.device_id} shell screencap -p',
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                shell=True
            )
            image_bytes = pipe.stdout.read().replace(b'\r\n', b'\n')
            if not image_bytes:
                return None
            
            # Convert bytes to numpy array
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            print(f"Error capture: {e}")
            return None

    @staticmethod
    def get_connected_devices():
        """Lấy danh sách thiết bị"""
        try:
            process = subprocess.Popen("adb devices", shell=True, stdout=subprocess.PIPE)
            output = process.stdout.read().decode('utf-8')
            devices = []
            for line in output.split('\n')[1:]:
                if '\tdevice' in line:
                    devices.append(line.split('\t')[0])
            return devices
        except:
            return []

# ==========================================
# PHẦN 2: CỬA SỔ CẮT ẢNH (CROP WINDOW)
# ==========================================
class RegionSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, cv2_image, device_id):
        super().__init__(parent)
        self.title(f"Cắt Ảnh Mẫu - {device_id}")
        self.geometry("1000x700")
        self.attributes("-topmost", True)
        self.focus_force()

        self.cv2_image = cv2_image
        
        # Convert ảnh OpenCV (BGR) sang PIL (RGB) để hiển thị lên Tkinter
        rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        self.pil_image = Image.fromarray(rgb_image)
        self.tk_image = ImageTk.PhotoImage(self.pil_image)

        # Frame chứa Canvas và thanh cuộn
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

        # Thanh cuộn
        self.v_scroll = ctk.CTkScrollbar(self.main_frame, orientation="vertical")
        self.h_scroll = ctk.CTkScrollbar(self.main_frame, orientation="horizontal")
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")

        # Canvas vẽ ảnh
        self.canvas = tk.Canvas(self.main_frame, bg="#2b2b2b", highlightthickness=0,
                                scrollregion=(0, 0, self.pil_image.width, self.pil_image.height),
                                yscrollcommand=self.v_scroll.set,
                                xscrollcommand=self.h_scroll.set,
                                cursor="cross")
        self.canvas.pack(side="left", expand=True, fill="both")

        self.v_scroll.configure(command=self.canvas.yview)
        self.h_scroll.configure(command=self.canvas.xview)
        
        # Vẽ ảnh lên canvas
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        # Variables vẽ hình chữ nhật
        self.rect_id = None
        self.start_x = 0
        self.start_y = 0

        # Bind chuột
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        # Hướng dẫn
        self.lbl_guide = ctk.CTkLabel(self, text="Kéo chuột để chọn vùng cần lấy mẫu. Nhả chuột để lưu.", text_color="yellow")
        self.lbl_guide.pack(side="bottom", pady=5)

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_id: self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="#00FF00", width=2)

    def on_move_press(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        x1, x2 = sorted([int(self.start_x), int(end_x)])
        y1, y2 = sorted([int(self.start_y), int(end_y)])

        if (x2 - x1) < 5 or (y2 - y1) < 5: return # Quá bé thì bỏ qua

        # Hộp thoại nhập tên
        dialog = ctk.CTkInputDialog(text="Đặt tên cho ảnh mẫu (Ví dụ: nut_mua):", title="Lưu Ảnh")
        filename = dialog.get_input()
        
        if filename:
            self.save_cropped_image(x1, y1, x2, y2, filename)
        else:
            self.canvas.delete(self.rect_id) # Hủy chọn nếu không nhập tên

    def save_cropped_image(self, x1, y1, x2, y2, filename):
        # Giới hạn tọa độ trong khung ảnh
        h, w = self.cv2_image.shape[:2]
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w, x2); y2 = min(h, y2)

        cropped_img = self.cv2_image[y1:y2, x1:x2]
        
        # Tạo folder lưu
        save_dir = "img_data"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        if not filename.endswith(".png"):
            filename += ".png"
            
        full_path = os.path.join(save_dir, filename)
        cv2.imwrite(full_path, cropped_img)
        print(f"✅ Đã lưu: {full_path}")
        
        self.destroy() # Đóng cửa sổ sau khi lưu

# ==========================================
# PHẦN 3: APP QUẢN LÝ (GIAO DIỆN CHÍNH)
# ==========================================
class CaptureToolApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Công Cụ Lấy Mẫu ADB (No Logic)")
        self.geometry("600x500")
        
        self.device_helpers = {} 

        # Cấu trúc Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_scan = ctk.CTkButton(self.header_frame, text="🔄 Quét Thiết Bị", command=self.scan_devices)
        self.btn_scan.pack(side="left", padx=10, pady=10)

        self.lbl_status = ctk.CTkLabel(self.header_frame, text="Sẵn sàng")
        self.lbl_status.pack(side="left", padx=10)

        # --- DANH SÁCH THIẾT BỊ ---
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Danh sách LDPlayer đang bật")
        self.scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # --- FOOTER ---
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        
        self.btn_open_folder = ctk.CTkButton(self.footer_frame, text="📂 Mở Thư Mục Ảnh", fg_color="gray", 
                                             command=lambda: os.startfile("img_data") if os.path.exists("img_data") else None)
        self.btn_open_folder.pack(side="right", padx=10, pady=5)

        # Tự động quét khi mở
        self.after(500, self.scan_devices)

    def scan_devices(self):
        self.lbl_status.configure(text="Đang quét ADB...")
        # Xóa danh sách cũ
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.device_helpers.clear()

        # Lấy danh sách mới
        devices = ADBHelper.get_connected_devices()
        
        if not devices:
            self.lbl_status.configure(text="Không tìm thấy thiết bị nào!")
            return

        for dev_id in devices:
            self.device_helpers[dev_id] = ADBHelper(dev_id)
            self.add_device_row(dev_id)

        self.lbl_status.configure(text=f"Đã kết nối: {len(devices)} thiết bị.")

    def add_device_row(self, device_id):
        row_frame = ctk.CTkFrame(self.scroll_frame)
        row_frame.pack(fill="x", pady=5)

        # Icon/Tên
        lbl_id = ctk.CTkLabel(row_frame, text=f"📱 {device_id}", width=200, anchor="w", font=("Arial", 14, "bold"))
        lbl_id.pack(side="left", padx=15, pady=10)

        # Nút Chụp & Cắt (Duy nhất)
        btn_capture = ctk.CTkButton(row_frame, text="📸 Chụp & Cắt", width=150, 
                                    fg_color="#E67E22", hover_color="#D35400",
                                    command=lambda d=device_id: self.start_capture_process(d))
        btn_capture.pack(side="right", padx=15, pady=10)

    def start_capture_process(self, device_id):
        """Chạy thread chụp để không đơ UI"""
        self.lbl_status.configure(text=f"Đang lấy hình ảnh từ {device_id}...")
        threading.Thread(target=self._capture_thread, args=(device_id,), daemon=True).start()

    def _capture_thread(self, device_id):
        adb = self.device_helpers.get(device_id)
        if adb:
            screen_img = adb.capture_screen()
            
            # Quay lại luồng chính để vẽ UI
            if screen_img is not None:
                self.after(0, lambda: self.open_crop_window(screen_img, device_id))
                self.after(0, lambda: self.lbl_status.configure(text="Đã lấy hình ảnh xong."))
            else:
                self.after(0, lambda: self.lbl_status.configure(text=f"Lỗi: Không chụp được {device_id}"))

    def open_crop_window(self, img, device_id):
        RegionSelectionDialog(self, img, device_id)

if __name__ == "__main__":
    app = CaptureToolApp()
    app.mainloop()