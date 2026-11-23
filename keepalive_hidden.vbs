Dim sh
Set sh = CreateObject("WScript.Shell")
Dim node, script, cmd
node = """C:\Users\luansha\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"""
script = """C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\keepalive_fs.mjs"""
cmd = node & " " & script
sh.Run cmd, 0, True
