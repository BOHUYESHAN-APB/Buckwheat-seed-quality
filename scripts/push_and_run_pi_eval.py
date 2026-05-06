import json
import os
import posixpath
import socket
from pathlib import Path

import paramiko


HOST = "192.168.11.239"
USER = "bhys"
PASSWORD_CANDIDATES = ["123456", "12345678"]
REMOTE_ROOT = "/home/bhys/buckwheat_v2_eval"


def connect_ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    last_error = None
    for password in PASSWORD_CANDIDATES:
        try:
            client.connect(HOST, username=USER, password=password, timeout=15, banner_timeout=15, auth_timeout=15)
            return client, password
        except Exception as exc:
            last_error = exc
    raise last_error


def sftp_mkdirs(sftp, remote_dir):
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}" if cur else f"/{part}"
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def upload_tree(sftp, local_root: Path, remote_root: str):
    for path in local_root.rglob("*"):
        rel = path.relative_to(local_root).as_posix()
        remote_path = posixpath.join(remote_root, rel)
        if path.is_dir():
            sftp_mkdirs(sftp, remote_path)
        else:
            sftp_mkdirs(sftp, posixpath.dirname(remote_path))
            sftp.put(str(path), remote_path)


def run(client, command):
    stdin, stdout, stderr = client.exec_command(command, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main():
    repo_root = Path(__file__).resolve().parents[1]
    staging = repo_root / "temp" / "pi_eval_bundle"
    if staging.exists():
        import shutil

        shutil.rmtree(staging)
    (staging / "model").mkdir(parents=True, exist_ok=True)
    (staging / "dataset" / "images" / "test").mkdir(parents=True, exist_ok=True)
    (staging / "dataset" / "labels" / "test").mkdir(parents=True, exist_ok=True)
    (staging / "scripts").mkdir(parents=True, exist_ok=True)

    local_best_onnx = repo_root / "temp" / "openi_run_bu_00" / "runs" / "buckwheat_yolo26n" / "weights" / "best.onnx"
    local_best_pt = repo_root / "temp" / "openi_run_bu_00" / "runs" / "buckwheat_yolo26n" / "weights" / "best.pt"
    data_yaml = repo_root / "temp" / "buckwheat_seed_dataset_v1" / "yolo_split" / "data.yaml"
    test_images = repo_root / "temp" / "buckwheat_seed_dataset_v1" / "yolo_split" / "images" / "test"
    test_labels = repo_root / "temp" / "buckwheat_seed_dataset_v1" / "yolo_split" / "labels" / "test"
    eval_script = repo_root / "scripts" / "pi_eval_onnx.py"

    import shutil

    shutil.copy2(local_best_onnx, staging / "model" / "best.onnx")
    shutil.copy2(local_best_pt, staging / "model" / "best.pt")
    shutil.copy2(data_yaml, staging / "dataset" / "data.yaml")
    shutil.copy2(eval_script, staging / "scripts" / "pi_eval_onnx.py")
    for file in test_images.glob("*"):
        if file.is_file():
            shutil.copy2(file, staging / "dataset" / "images" / "test" / file.name)
    for file in test_labels.glob("*"):
        if file.is_file():
            shutil.copy2(file, staging / "dataset" / "labels" / "test" / file.name)

    client, password = connect_ssh()
    sftp = client.open_sftp()
    sftp_mkdirs(sftp, REMOTE_ROOT)
    upload_tree(sftp, staging, REMOTE_ROOT)

    setup_cmd = (
        "set -e; "
        f"mkdir -p {REMOTE_ROOT}/output; "
        "python3 - <<'PY'\n"
        "mods=['onnxruntime','cv2','numpy'];\n"
        "missing=[]\n"
        "import importlib\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except Exception:\n"
        "        missing.append(m)\n"
        "print('MISSING=' + ','.join(missing))\n"
        "PY"
    )
    code1, out1, err1 = run(client, setup_cmd)

    eval_cmd = (
        "set -e; "
        f"cd {REMOTE_ROOT}; "
        "python3 scripts/pi_eval_onnx.py "
        f"--model {REMOTE_ROOT}/model/best.onnx "
        f"--image_dir {REMOTE_ROOT}/dataset/images/test "
        f"--labels_dir {REMOTE_ROOT}/dataset/labels/test "
        f"--output_dir {REMOTE_ROOT}/output "
        "--imgsz 960 --repeats 5 --fps 12 --seconds 3"
    )
    code2, out2, err2 = run(client, eval_cmd)

    report = {
        "password_used": password,
        "setup": {"code": code1, "stdout": out1, "stderr": err1},
        "eval": {"code": code2, "stdout": out2, "stderr": err2},
        "remote_root": REMOTE_ROOT,
    }
    report_path = staging / "pi_push_run_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)

    sftp.close()
    client.close()


if __name__ == "__main__":
    main()
