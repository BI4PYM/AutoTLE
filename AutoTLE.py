import subprocess

output = subprocess.run("date /t   && time /t", shell=True, capture_output=True, text=True).stdout
print(output)
output1 = '\n' + subprocess.run("git pull origin master", shell=True, capture_output=True, text=True).stdout
print(output1)
output2 = '\n' + subprocess.run("python main.py", shell=True, capture_output=True, text=True).stdout
print(output2)
output3 = '\n' + subprocess.run("git add *", shell=True, capture_output=True, text=True).stdout
print(output3)
output4 = '\n' + subprocess.run("git add logs.txt'", shell=True, capture_output=True, text=True).stdout
print(output4)
output5 = '\n' + subprocess.run("git commit -a -m 'Auto upload'", shell=True, capture_output=True, text=True).stdout
print(output5)
output6 = '\n' + subprocess.run("git push -u --force origin master", shell=True, capture_output=True, text=True).stdout
print(output6)
output = output + output1 + output2 + output3 + output4 + output5 + output6
with open("logs.txt", "w") as file:
    file.write(output)
