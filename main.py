import customtkinter as ctk
import threading
import os
from adb_manager import ADBHelper
from gui import RegionSelectionDialog  # <-- Import class từ file gui.py

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CaptureToolApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Công Cụ Lấy Mẫu ADB Pro (Zoom & ROI)")

        # Căn giữa màn hình
        w, h = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self.device_helpers = {} 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.btn_scan = ctk.CTkButton(self.header_frame, text="🔄 Quét Thiết Bị", command=self.scan_devices)
        self.btn_scan.pack(side="left", padx=10, pady=10)
        self.lbl_status = ctk.CTkLabel(self.header_frame, text="Sẵn sàng")
        self.lbl_status.pack(side="left", padx=10)

        # List
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="Danh sách LDPlayer")
        self.scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Footer
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.btn_open_folder = ctk.CTkButton(self.footer_frame, text="📂 Mở Thư Mục Ảnh", fg_color="gray", 
                                             command=lambda: os.startfile("img_data") if os.path.exists("img_data") else None)
        self.btn_open_folder.pack(side="right", padx=10, pady=5)

        self.after(500, self.scan_devices)

    def scan_devices(self):
        self.lbl_status.configure(text="Đang quét ADB...")
        for widget in self.scroll_frame.winfo_children(): widget.destroy()
        self.device_helpers.clear()

        devices = ADBHelper.get_connected_devices()
        if not devices:
            self.lbl_status.configure(text="Không tìm thấy thiết bị!")
            return

        for dev_id in devices:
            self.device_helpers[dev_id] = ADBHelper(dev_id)
            self.add_device_row(dev_id)
        self.lbl_status.configure(text=f"Đã kết nối: {len(devices)} thiết bị.")

    def add_device_row(self, device_id):
        row = ctk.CTkFrame(self.scroll_frame)
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=f"📱 {device_id}", width=200, anchor="w", font=("Arial", 14, "bold")).pack(side="left", padx=15, pady=10)
        ctk.CTkButton(row, text="📸 Mở Công Cụ Cắt", width=150, fg_color="#E67E22", hover_color="#D35400",
                      command=lambda d=device_id: self.start_capture_process(d)).pack(side="right", padx=15, pady=10)

    def start_capture_process(self, device_id):
        self.lbl_status.configure(text=f"Đang lấy hình ảnh từ {device_id}...")
        threading.Thread(target=self._capture_thread, args=(device_id,), daemon=True).start()

    def _capture_thread(self, device_id):
        adb = self.device_helpers.get(device_id)
        if adb:
            screen_img = adb.capture_screen()
            if screen_img is not None:
                # Gọi class từ file gui.py
                self.after(0, lambda: RegionSelectionDialog(self, screen_img, device_id, adb))
                self.after(0, lambda: self.lbl_status.configure(text="Đã mở cửa sổ cắt."))
            else:
                self.after(0, lambda: self.lbl_status.configure(text=f"Lỗi chụp {device_id}"))

if __name__ == "__main__":
    app = CaptureToolApp()
    app.mainloop()