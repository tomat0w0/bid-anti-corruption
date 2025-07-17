#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招标廉政体检系统启动脚本

该脚本用于启动整个系统，包括后端API服务和前端Streamlit应用。
支持开发模式和生产模式。
"""

import os
import sys
import subprocess
import time
import signal
import argparse
from pathlib import Path
from typing import List, Optional

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

class SystemManager:
    """系统管理器"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n收到信号 {signum}，正在关闭系统...")
        self.stop_all()
        sys.exit(0)
    
    def check_dependencies(self) -> bool:
        """检查依赖是否安装"""
        print("🔍 检查系统依赖...")
        
        # 检查Python版本
        if sys.version_info < (3, 8):
            print("❌ 需要Python 3.8或更高版本")
            return False
        
        # 检查后端依赖
        backend_requirements = BACKEND_DIR / "requirements.txt"
        if not backend_requirements.exists():
            print(f"❌ 后端依赖文件不存在: {backend_requirements}")
            return False
        
        # 检查前端依赖
        frontend_requirements = FRONTEND_DIR / "requirements.txt"
        if not frontend_requirements.exists():
            print(f"❌ 前端依赖文件不存在: {frontend_requirements}")
            return False
        
        print("✅ 依赖检查通过")
        return True
    
    def install_dependencies(self, force: bool = False):
        """安装依赖"""
        if not force:
            response = input("是否安装/更新依赖包？(y/N): ")
            if response.lower() != 'y':
                return
        
        print("📦 安装后端依赖...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", 
                str(BACKEND_DIR / "requirements.txt")
            ], check=True, cwd=BACKEND_DIR)
            print("✅ 后端依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 后端依赖安装失败: {e}")
            return False
        
        print("📦 安装前端依赖...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", 
                str(FRONTEND_DIR / "requirements.txt")
            ], check=True, cwd=FRONTEND_DIR)
            print("✅ 前端依赖安装完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 前端依赖安装失败: {e}")
            return False
        
        return True
    
    def setup_environment(self):
        """设置环境变量"""
        env_file = PROJECT_ROOT / ".env"
        env_example = PROJECT_ROOT / ".env.example"
        
        if not env_file.exists() and env_example.exists():
            print("📝 创建环境配置文件...")
            try:
                import shutil
                shutil.copy(env_example, env_file)
                print(f"✅ 已创建 {env_file}")
                print("⚠️  请编辑 .env 文件配置必要的环境变量")
            except Exception as e:
                print(f"❌ 创建环境文件失败: {e}")
    
    def start_backend(self, dev_mode: bool = True, port: int = 8000) -> Optional[subprocess.Popen]:
        """启动后端服务"""
        print(f"🚀 启动后端服务 (端口: {port})...")
        
        try:
            if dev_mode:
                # 开发模式：使用uvicorn的热重载
                cmd = [
                    sys.executable, "-m", "uvicorn", 
                    "app:app", 
                    "--host", "0.0.0.0", 
                    "--port", str(port),
                    "--reload",
                    "--reload-dir", "."
                ]
            else:
                # 生产模式
                cmd = [
                    sys.executable, "-m", "uvicorn", 
                    "app:app", 
                    "--host", "0.0.0.0", 
                    "--port", str(port),
                    "--workers", "4"
                ]
            
            process = subprocess.Popen(
                cmd,
                cwd=BACKEND_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append(process)
            print(f"✅ 后端服务已启动 (PID: {process.pid})")
            return process
            
        except Exception as e:
            print(f"❌ 启动后端服务失败: {e}")
            return None
    
    def start_frontend(self, port: int = 8501) -> Optional[subprocess.Popen]:
        """启动前端服务"""
        print(f"🎨 启动前端服务 (端口: {port})...")
        
        try:
            cmd = [
                sys.executable, "-m", "streamlit", "run", 
                "streamlit_app.py",
                "--server.port", str(port),
                "--server.address", "0.0.0.0",
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false"
            ]
            
            process = subprocess.Popen(
                cmd,
                cwd=FRONTEND_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append(process)
            print(f"✅ 前端服务已启动 (PID: {process.pid})")
            return process
            
        except Exception as e:
            print(f"❌ 启动前端服务失败: {e}")
            return None
    
    def wait_for_service(self, url: str, timeout: int = 30) -> bool:
        """等待服务启动"""
        import requests
        
        print(f"⏳ 等待服务启动: {url}")
        
        for i in range(timeout):
            try:
                response = requests.get(url, timeout=1)
                if response.status_code == 200:
                    print(f"✅ 服务已就绪: {url}")
                    return True
            except:
                pass
            
            time.sleep(1)
            if i % 5 == 0:
                print(f"⏳ 等待中... ({i}/{timeout}s)")
        
        print(f"❌ 服务启动超时: {url}")
        return False
    
    def stop_all(self):
        """停止所有服务"""
        print("🛑 停止所有服务...")
        
        for process in self.processes:
            if process.poll() is None:  # 进程仍在运行
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"✅ 进程 {process.pid} 已停止")
                except subprocess.TimeoutExpired:
                    print(f"⚠️  强制终止进程 {process.pid}")
                    process.kill()
                except Exception as e:
                    print(f"❌ 停止进程 {process.pid} 失败: {e}")
        
        self.processes.clear()
    
    def show_status(self):
        """显示系统状态"""
        print("\n📊 系统状态:")
        print(f"后端服务: http://localhost:8000")
        print(f"前端应用: http://localhost:8501")
        print(f"API文档: http://localhost:8000/docs")
        print(f"运行进程: {len([p for p in self.processes if p.poll() is None])} 个")
        print("\n按 Ctrl+C 停止系统")
    
    def run(self, dev_mode: bool = True, install_deps: bool = False, 
            backend_port: int = 8000, frontend_port: int = 8501):
        """运行系统"""
        print("🔍 招标廉政体检系统启动器")
        print("=" * 50)
        
        # 检查依赖
        if not self.check_dependencies():
            return False
        
        # 安装依赖
        if install_deps:
            if not self.install_dependencies(force=True):
                return False
        
        # 设置环境
        self.setup_environment()
        
        try:
            # 启动后端
            backend_process = self.start_backend(dev_mode, backend_port)
            if not backend_process:
                return False
            
            # 等待后端启动
            if not self.wait_for_service(f"http://localhost:{backend_port}/health", 30):
                print("❌ 后端服务启动失败")
                self.stop_all()
                return False
            
            # 启动前端
            frontend_process = self.start_frontend(frontend_port)
            if not frontend_process:
                self.stop_all()
                return False
            
            # 等待前端启动
            time.sleep(3)
            
            # 显示状态
            self.show_status()
            
            # 监控进程
            while True:
                time.sleep(1)
                
                # 检查进程状态
                for process in self.processes[:]:
                    if process.poll() is not None:
                        print(f"⚠️  进程 {process.pid} 已退出")
                        self.processes.remove(process)
                
                # 如果所有进程都退出了，停止系统
                if not self.processes:
                    print("❌ 所有服务已停止")
                    break
        
        except KeyboardInterrupt:
            print("\n👋 用户中断")
        except Exception as e:
            print(f"❌ 系统运行错误: {e}")
        finally:
            self.stop_all()
        
        return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="招标廉政体检系统启动器")
    parser.add_argument(
        "--mode", 
        choices=["dev", "prod"], 
        default="dev",
        help="运行模式 (dev: 开发模式, prod: 生产模式)"
    )
    parser.add_argument(
        "--install-deps", 
        action="store_true",
        help="自动安装依赖包"
    )
    parser.add_argument(
        "--backend-port", 
        type=int, 
        default=8000,
        help="后端服务端口 (默认: 8000)"
    )
    parser.add_argument(
        "--frontend-port", 
        type=int, 
        default=8501,
        help="前端服务端口 (默认: 8501)"
    )
    
    args = parser.parse_args()
    
    manager = SystemManager()
    success = manager.run(
        dev_mode=(args.mode == "dev"),
        install_deps=args.install_deps,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()