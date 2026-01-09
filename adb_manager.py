import subprocess
import os
import cv2
import numpy as np

class ADBHelper:
    def __init__(self, device_id):
        self.device_id = device_id
        # Tự động lấy đường dẫn ADB
        self.adb_path = self._get_adb_executable()

    @staticmethod
    def _get_adb_executable():
        """
        Hàm nội bộ: Tìm file adb.exe nằm cùng thư mục code.
        Nếu có -> trả về đường dẫn tuyệt đối.
        Nếu không -> trả về 'adb' (dùng biến môi trường).
        """
        # Lấy đường dẫn thư mục hiện tại chứa file script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Đường dẫn tới file adb trong folder 'adb'
        local_adb = os.path.join(current_dir, "adb", "adb.exe")

        if os.path.exists(local_adb):
            return f'"{local_adb}"' # Thêm ngoặc kép để tránh lỗi khoảng trắng
        return "adb"

    def capture_screen(self):
        """Chụp màn hình -> OpenCV Image"""
        try:
            # Sửa lệnh cmd để dùng self.adb_path đã tìm được
            cmd = f'{self.adb_path} -s {self.device_id} shell screencap -p'
            
            # Cấu hình để ẩn cửa sổ CMD đen xì khi chạy (chỉ có tác dụng trên Windows)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            pipe = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Bắt thêm stderr để không hiện rác
                shell=True,
                startupinfo=startupinfo
            )
            image_bytes = pipe.stdout.read().replace(b'\r\n', b'\n')
            
            if not image_bytes: return None
            
            return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Error capture: {e}")
            return None

    @staticmethod
    def get_connected_devices():
        try:
            # Lấy đường dẫn ADB
            adb_cmd = ADBHelper._get_adb_executable()
            
            # Ẩn cửa sổ CMD
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(
                f"{adb_cmd} devices", 
                shell=True, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )
            output = process.stdout.read().decode('utf-8')
            devices = []
            for line in output.split('\n')[1:]:
                if '\tdevice' in line:
                    devices.append(line.split('\t')[0])
            return devices
        except: return []