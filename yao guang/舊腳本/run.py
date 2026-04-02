import subprocess
import os

def run_script(script_name):
    try:
        script_path = os.path.join('script', script_name)
        result = subprocess.run(['python', script_path], check=True, text=True, capture_output=True)
        print(f"Script {script_name} ran successfully:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error running script {script_name}:\n{e.stderr}")

def main():
    scripts = ['01.py', '02.py', '03.py', '04.py', '05.py', '06.py', '07.py']
    for script in scripts:
        run_script(script)

if __name__ == "__main__":
    main()
