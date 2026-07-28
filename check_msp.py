import win32com.client

app = win32com.client.Dispatch("MSProject.Application")
print("OK", app)
app.Quit()
