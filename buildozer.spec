[app]
title = Nilgiri Dairy App
package.name = nilgiridairy
package.domain = org.nilgiridairy

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx,whl,ttf,json

version = 1.0

# Scanner ke liye requests aur zaroori network modules add kar diye hain
requirements = python3,kivy,requests,urllib3,charset_normalizer,idna,certifi,openpyxl,androidstorage4kivy

# Internet aur Camera/Storage permissions zaroori hain
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA

orientation = portrait
fullscreen = 0

android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
