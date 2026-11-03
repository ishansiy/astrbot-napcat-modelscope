"""Download a complete remote backup folder first; restore into a NEW empty folder."""
import argparse
from pathlib import Path
from core import restore_bundle
parser=argparse.ArgumentParser(description='解密、校验并恢复大肥鱼备份到空目录，不直接覆盖运行中的服务。')
parser.add_argument('--bundle',required=True,help='含 manifest.json 与全部 part-*.bin 的本地目录')
parser.add_argument('--key-file',required=True,help='保存恢复密钥的本地文件，密钥不放在命令行')
parser.add_argument('--output',required=True,help='新的空恢复目录')
args=parser.parse_args()
print(restore_bundle(args.bundle,Path(args.key_file).read_text(encoding='utf-8-sig').strip(),args.output))
