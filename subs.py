import os
import subprocess
import sys
import platform

system_info = platform.system()

if system_info == 'Windows':
    mkvmerge = "C:\\Program Files\\MKVToolNix\\mkvmerge.exe"
elif system_info == 'Linux':
    mkvmerge = "/usr/bin/mkvmerge"
else: #unixlike
    mkvmerge = "/usr/bin/mkvmerge"


def create_output_directory(directory):
    if not os.path.exists(os.path.join(directory, "Output")):
        os.mkdir(os.path.join(directory, "Output"))


def process_files(directory):
    files = [file for file in os.listdir(directory) if file.endswith(".mp4") or file.endswith(".mkv")]

    for file in files:
        input_file = os.path.join(directory, file)
        output_file = os.path.join(os.path.join(directory, "Output"), file)
        ass_file = os.path.join(directory, f"{os.path.splitext(file)[0]}.ass")
        srt_file = os.path.join(directory, f"{os.path.splitext(file)[0]}.srt")
        ssa_file = os.path.join(directory, f"{os.path.splitext(file)[0]}.ssa")

        subprocess.run(
            [mkvmerge, "-o", output_file, input_file, "--track-name", "0:Spanish", "--language", "0:spa", ass_file])
        subprocess.run(
            [mkvmerge, "-o", output_file, input_file, "--track-name", "0:Spanish", "--language", "0:spa", srt_file])
        subprocess.run(
            [mkvmerge, "-o", output_file, input_file, "--track-name", "0:Spanish", "--language", "0:spa", ssa_file])
        
if __name__ == "__main__":

    input_directory = input("introduzca el path:")
    create_output_directory(input_directory)
    process_files(input_directory)

    print("\n============================ :)")
    input("Hecho. Presiona cualquier tecla para salir.")
