[app]
title = Nilgiri Dairy App
package.name = nilgiridairy
package.domain = org.nilgiridairy
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx,whl,ttf,json
version = 1.0

# 403 Error se bachne ke liye safe requirements
requirements = python3,kivy,requests,certifi,urllib3,chardet,idna

android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.allow_backup = True

# NDK 28 Crash aur Broken Pipe Fix (Must be under [app])
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

[buildozer]
log_level = 2
warn_on_root = 1
