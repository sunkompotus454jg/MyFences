import winreg
import os
import sys

def add_to_context_menu():
    script_path = os.path.abspath("main.py")
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    command = f'"{python_exe}" "{script_path}" --create'
    
  
    key_path = r"Directory\Background\shell\MyFences"
    
    try:
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path)
        winreg.SetValue(key, "", winreg.REG_SZ, "🟦 Создать Сетку (Fences)")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, "explorer.exe") # Иконка папки
        command_key = winreg.CreateKey(key, "command")
        winreg.SetValue(command_key, "", winreg.REG_SZ, command)
        
        print("Успех! Кликни правой кнопкой мыши по рабочему столу.")
    except Exception as e:
        print(f"Ошибка (запустите от имени Администратора!): {e}")

if __name__ == "__main__":
    add_to_context_menu()