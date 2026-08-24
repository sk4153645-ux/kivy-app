[app]
title = MyApp
package.name = myapp
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1
requirements = python3==3.11.9,hostpython3==3.11.9,kivy
orientation = portrait
fullscreen = 0
android.archs = arm64-v8a
android.allow_backup = True

# Use our patched python-for-android (fixes a pip self-upgrade bug in
# p4a's own build.py — see build.yml "Clone and patch python-for-android"
# step, which creates this directory fresh on every run).
p4a.source_dir = ./p4a-patched

[buildozer]
log_level = 2
warn_on_root = 1
