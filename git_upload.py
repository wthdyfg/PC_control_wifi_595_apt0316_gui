import os
import subprocess
import sys
import platform

def find_git():
    # 1. 尝试直接调用
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return "git"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # 2. 搜索常见路径 (Windows)
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\Git\cmd\git.exe",
            r"C:\Program Files\Git\bin\git.exe",
            r"C:\Program Files (x86)\Git\cmd\git.exe",
            r"C:\Users\{}\AppData\Local\Programs\Git\cmd\git.exe".format(os.environ.get("USERNAME", "")),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    return None

def run_git_command(git_exe, args, cwd=None):
    cmd = [git_exe] + args
    try:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, encoding='utf-8')
        if result.returncode != 0:
            return False, result.stderr
        return True, result.stdout.strip()
    except Exception as e:
        return False, str(e)

def main():
    print("==========================================")
    print("       Git 仓库初始化与上传助手 (Python版)")
    print("==========================================")
    
    # 1. 检测 Git
    print("\n[1/5] 正在检测 Git 环境...")
    git_exe = find_git()
    if not git_exe:
        print("\n[错误] 未在系统中找到 Git！")
        print("请先下载并安装 Git: https://git-scm.com/downloads")
        print("如果是默认安装，脚本会自动找到它。")
        return

    print(f"Git 已找到: {git_exe}")

    # 2. 初始化
    if not os.path.exists(".git"):
        print("\n[2/5] 初始化 Git 仓库...")
        success, msg = run_git_command(git_exe, ["init"])
        if success:
            print("仓库初始化完成。")
        else:
            print(f"初始化失败: {msg}")
            return
    else:
        print("\n[2/5] 仓库已存在，跳过初始化。")

    # 2.5 检查 Git 配置
    print("\n[2.5] 检查 Git 用户配置...")
    success, email = run_git_command(git_exe, ["config", "user.email"])
    if not success or not email:
        print("检测到未配置 Git 用户信息，正在自动配置默认值...")
        run_git_command(git_exe, ["config", "--local", "user.email", "trae@assistant.com"])
        run_git_command(git_exe, ["config", "--local", "user.name", "Trae Assistant"])
    else:
        print(f"Git 用户已配置: {email}")

    # 3. 提交代码
    print("\n[3/5] 添加并提交文件...")
    run_git_command(git_exe, ["add", "."])
    
    # 检查是否有变更需要提交
    success, status = run_git_command(git_exe, ["status", "--porcelain"])
    if not success or not status:
        print("没有检测到新的更改，跳过提交。")
    else:
        success, msg = run_git_command(git_exe, ["commit", "-m", "Initial commit: 项目初始化 (由 Trae 助手生成)"])
        if success:
            print("代码提交成功。")
        else:
            print(f"提交失败: {msg}")

    # 4. 关联远程
    print("\n[4/5] 关联远程仓库")
    remote_url = input("请输入远程仓库地址 (例如 https://github.com/user/repo.git，直接回车跳过): ").strip()
    
    if not remote_url:
        print("已跳过远程关联。")
    else:
        # 检查 origin 是否存在
        success, _ = run_git_command(git_exe, ["remote", "get-url", "origin"])
        if success:
            print("检测到 origin 已存在，正在更新...")
            run_git_command(git_exe, ["remote", "set-url", "origin", remote_url])
        else:
            run_git_command(git_exe, ["remote", "add", "origin", remote_url])
            
        # 5. 推送
        print("\n[5/5] 正在推送到远程仓库...")
        # 尝试重命名分支为 main
        run_git_command(git_exe, ["branch", "-M", "main"])
        
        while True:
            print(f"正在推送到: {remote_url}")
            print("注意: 可能会弹出浏览器窗口要求验证，请留意任务栏...")
            success, msg = run_git_command(git_exe, ["push", "-u", "origin", "main"])
            
            if success:
                print("\n[成功] 项目已成功上传！")
                break
            else:
                print(f"\n[失败] 推送失败: {msg}")
                print("常见原因: 1. 地址错误 2. 权限不足 3. 仓库非空")
                retry = input("是否修改地址并重试？(y/n): ").strip().lower()
                if retry == 'y':
                    remote_url = input("请输入新的远程仓库地址: ").strip()
                    if remote_url:
                        run_git_command(git_exe, ["remote", "set-url", "origin", remote_url])
                else:
                    break

    print("\n==========================================")
    print("               操作结束")
    print("==========================================")

if __name__ == "__main__":
    main()
