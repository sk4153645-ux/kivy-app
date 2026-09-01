[app]
# (str) Title of your application
title = Nilgiri Dairy App

# (str) Package name
package.name = nilgiridairy

# (str) Package domain (needed for android/ios packaging)
package.domain = org.nilgiridairy

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx,ttf,json

# (str) Application version
version = 1.0

# (list) Application requirements (Pure wheels, no local .whl paths)
requirements = python3==3.11.9,hostpython3==3.11.9,kivy,requests,certifi,urllib3,chardet,idna,openpyxl,fpdf2,plyer

# (list) Permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA,READ_MEDIA_IMAGES,BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,SEND_SMS

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate whether the screen should be fullscreen
fullscreen = 0

# (list) The Android archs to build for
android.archs = arm64-v8a

# (bool) Android allow backup
android.allow_backup = True

# (str) Icon & Splash of the application
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png

# (str) Android NDK/SDK Paths
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2
android.accept_sdk_license = True

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
