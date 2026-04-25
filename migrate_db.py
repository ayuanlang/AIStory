import os
import sys
import subprocess

# Render 远端数据库（源数据库）
SOURCE_DB_URL = "postgresql://aistory_user:857R3uszoXImWFYBNC2wNTtXNoc0fpIt@dpg-d61o097gi27c73es1jo0-a.oregon-postgres.render.com/aistory_tm6i"

# 阿里云 数据库（目标数据库）
# 请替换为您在阿里云机器上的 PostgreSQL 实际账号密码、地址和库名
# 例如：postgresql://aistory_user:your_password@localhost:5432/aistory_db
TARGET_DB_URL = "postgresql://aistory:yl.415213@127.0.0.1:5432/aistory"

def check_dependencies():
    """检查是否安装了 PostgreSQL 客户端工具"""
    try:
        subprocess.run(["pg_dump", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(["psql", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError:
        print("❌ 错误：未找到 pg_dump 或 psql 命令。")
        print("请确保已安装 PostgreSQL 客户端工具。")
        print("  - Ubuntu/Debian 上执行: apt-get install postgresql-client")
        print("  - Windows 上请将 postgresql 的 bin 目录加入环境变量。")
        sys.exit(1)

def migrate_database():
    if "<ALIYUN_DB_USER>" in TARGET_DB_URL:
        print("⚠️ 请先在脚本中修改 TARGET_DB_URL 为您的阿里云真实数据库连接信息！")
        sys.exit(1)

    print("🚀 开始数据库迁移流程...")
    print("👉 源端: Render (Oregon 区)")
    print("👉 目的: 阿里云数据库")
    
    # 使用流式传输直接对拷（不在本地落盘），不仅快，而且省空间
    # -O: 不导出所有者 (让阿里云接管)
    # -x: 不导出全库权限
    # -c: 导入前先 DROP 掉已有的同名表（防止冲突）
    dump_cmd = ["pg_dump", SOURCE_DB_URL, "-O", "-x", "-c", "--if-exists"]
    restore_cmd = ["psql", TARGET_DB_URL]

    print("\n⏳ 正在传输数据... (根据数据量大小可能需要几分钟，请耐心等待)")
    try:
        # 直接管道对拷 pg_dump | psql
        dump_proc = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE)
        restore_proc = subprocess.Popen(restore_cmd, stdin=dump_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 允许 dump 进程收到 SIGPIPE
        dump_proc.stdout.close()
        
        # 等待导入完成
        stdout, stderr = restore_proc.communicate()
        
        if restore_proc.returncode != 0:
            print("❌ 导入过程中发生错误:")
            print(stderr.decode('utf-8', errors='ignore'))
        else:
            print("✅ 数据库迁移成功！所有表结构和数据已平滑迁移至阿里云！")
            
    except Exception as e:
        print(f"❌ 发生异常: {e}")

if __name__ == "__main__":
    check_dependencies()
    migrate_database()
