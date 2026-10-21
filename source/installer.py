# -*- coding: utf-8 -*-
"""Aterl-DistSim 安装器: 内嵌程序文件, 安装到 %LOCALAPPDATA%\\Programs\\Aterl-DistSim
   用 PyInstaller --onefile --add-data 打包"""
import sys, os, shutil, subprocess
from pathlib import Path


def resource(name):
    """取内嵌资源 (PyInstaller onefile 运行时在 sys._MEIPASS)"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def create_shortcut(lnk_path, target, workdir):
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}');"
          f"$s.TargetPath='{target}';$s.WorkingDirectory='{workdir}';$s.Save()")
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-Command', ps], capture_output=True)


def main():
    print("=" * 50)
    print("  Aterl-DistSim v1.0 安装程序")
    print("=" * 50)
    target = Path(os.environ.get('ATERL_INSTALL_DIR',
                                 str(Path(os.environ['LOCALAPPDATA']) / 'Programs' / 'Aterl-DistSim')))
    print(f"\n安装目录: {target}")
    target.mkdir(parents=True, exist_ok=True)

    files = ['Aterl-DistSim.exe', 'config.json', 'cases.jsonl']
    for f in files:
        src = resource(f)
        if os.path.exists(src):
            shutil.copy2(src, target / f)
            print(f"  复制: {f}")

    (target / 'logs').mkdir(exist_ok=True)

    desktop = Path(os.environ['USERPROFILE']) / 'Desktop'
    startmenu = Path(os.environ['APPDATA']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs'
    exe = str(target / 'Aterl-DistSim.exe')
    create_shortcut(str(desktop / 'Aterl-DistSim.lnk'), exe, str(target))
    create_shortcut(str(startmenu / 'Aterl-DistSim.lnk'), exe, str(target))
    print("  已创建桌面/开始菜单快捷方式")

    print("\n" + "=" * 50)
    print("  安装完成！")
    print(f"  程序位置: {target}")
    print("=" * 50)
    try:
        input("\n按回车键退出...")
    except EOFError:
        pass


if __name__ == '__main__':
    main()
