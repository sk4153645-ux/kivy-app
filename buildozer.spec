[app]
title = Nilgiri Dairy App
package.name = nilgiridairy
package.domain = org.nilgiridairy
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx,whl,ttf,json
version = 1.0
requirements = python3==3.11.9,hostpython3==3.11.9,kivy,requests,certifi,urllib3,chardet,idna,openpyxl,./reportlab-5.0.0-py3-none-any.whl,plyer
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA,READ_MEDIA_IMAGES,BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,SEND_SMS
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.allow_backup = True

# Logo and Splash Screen Links
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png

# Android SDK/NDK Paths
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/27.3.13750724
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
