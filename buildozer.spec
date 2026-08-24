[app]
title = Dairy Hisaab
package.name = dairyhisaab
package.domain = org.dairyhisaab
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,xlsx
version = 1.0

requirements = python3,kivy,openpyxl,reportlab,androidstorage4kivy

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
