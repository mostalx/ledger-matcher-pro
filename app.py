
from flask import Flask, send_from_directory, jsonify
import subprocess
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "dashboard"),
    template_folder=os.path.join(BASE_DIR, "dashboard")
)


@app.route('/')
def index():
    return send_from_directory(
        os.path.join(BASE_DIR, "dashboard"),
        'index.html'
    )


@app.route('/api/run-simulation', methods=['POST'])
def run_simulation():
    try:
        # Use the exact Python interpreter running Flask
        generator = subprocess.run(
            [sys.executable, 'generate_data.py'],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True
        )

        matcher = subprocess.run(
            [sys.executable, 'main.py'],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True
        )

        return jsonify({
            "status": "success",
            "message": "Pipeline completed successfully!",
            "output": matcher.stdout
        })

    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "error",
            "message": (
                f"Command failed: {e.cmd}\n"
                f"Exit code: {e.returncode}\n"
                f"Error details:\n{e.stderr or e.stdout}"
            )
        }), 500

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)