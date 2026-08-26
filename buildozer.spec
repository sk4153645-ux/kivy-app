[app]
title = Nilgiri Dairy App
package.name = nilgiridairy
package.domain = org.nilgiridairy

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx,whl,ttf,json

version = 1.0

# Poore features (Excel + Storage + Network/AI)
requirements = python3,kivy,requests,openpyxl,androidstorage4kivy

# Permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA

orientation = portrait
fullscreen = 0

android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
