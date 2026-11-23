Dim sh
Set sh = CreateObject("WScript.Shell")
Dim cmd
cmd = """" & "C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13\agg_board_1122\pipeline\run_pipeline.cmd" & """"
sh.Run cmd, 0, True
