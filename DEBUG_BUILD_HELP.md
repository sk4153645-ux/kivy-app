# 🔧 Nilgiri Dairy App - Build Troubleshooting Guide

## Quick Start

### Run Local Validation
```bash
chmod +x BUILD_CONFIG_VALIDATION.sh
./BUILD_CONFIG_VALIDATION.sh
```

### Build Locally
```bash
buildozer -v android debug
```

---

## 📋 Prerequisites Checklist

### System Requirements
- [ ] Python 3.7+
- [ ] Java 11+ (OpenJDK 17 recommended)
- [ ] 20GB+ free disk space
- [ ] Linux/macOS/WSL (Windows requires WSL2)

### Installation
```bash
# Install Buildozer
pip install buildozer==1.5.0 Cython==0.29.36 virtualenv

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install openjdk-17-jdk git zip unzip openjdk-17-jdk autoconf automake libtool pkg-config

# Verify
buildozer --version
java -version
python3 --version
```

---

## 🔴 Common Build Failures & Fixes

### ❌ Error: "buildozer: command not found"
**Solution:**
```bash
pip install buildozer==1.5.0
python -m buildozer --version
```

### ❌ Error: "No module named 'buildozer'"
**Solution:**
```bash
pip install --upgrade pip
pip install buildozer Cython virtualenv
```

### ❌ Error: "JDK not found" / "JAVA_HOME not set"
**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install openjdk-17-jdk

# Verify
java -version
javac -version

# If not in PATH, set manually
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
```

### ❌ Error: "NDK not found" / "NDK download failed"
**Solution:**
This is normal on first build. Buildozer will download it automatically (~2GB).
- Ensure you have 30GB+ free disk space
- Check internet connection
- Clear cache if stuck:
  ```bash
  rm -rf ~/.buildozer
  buildozer android clean
  ```

### ❌ Error: "Gradle build failed"
**Solutions:**
1. Clear Gradle cache:
   ```bash
   rm -rf ~/.gradle/caches
   buildozer android clean
   ```

2. Check buildozer.spec:
   - `android.api` should be 31+
   - `android.minapi` should be 21+
   - `android.ndk` should match available NDK version

3. Check requirements.txt for conflicting packages

### ❌ Error: "requirements not found" / "Python package X failed"
**Solution:**
1. Verify `buildozer.spec` `requirements` line:
   ```ini
   requirements = python3,kivy==2.3.0,requests,certifi,urllib3,chardet,idna,openpyxl,reportlab
   ```

2. Check `requirements.txt` exists and is valid:
   ```bash
   cat requirements.txt
   ```

3. Test locally:
   ```bash
   pip install kivy requests openpyxl reportlab
   ```

### ❌ Error: "Invalid X.509 certificate"
**Solution:**
Update certificates:
```bash
pip install --upgrade certifi
# On macOS:
/Applications/Python\ 3.x/Install\ Certificates.command
```

### ❌ Error: "Out of memory" / "Build timeout"
**Solution:**
1. Close other applications
2. Increase timeout in workflow (GitHub Actions):
   ```yaml
   timeout-minutes: 120
   ```
3. Clear caches:
   ```bash
   buildozer android clean
   rm -rf ~/.buildozer ~/.gradle
   ```

### ❌ Error: "Module X not found" (e.g., "No module named 'dairy_ai_scanner'")
**Solution:**
Ensure all required files exist in project root:
- [ ] `main.py`
- [ ] `buildozer.spec`
- [ ] `requirements.txt`
- [ ] `dairy_ai_scanner.py` (if using AI Scanner)
- [ ] Any other `.py` files imported in main.py

### ❌ Error: "APK not generated" / "bin directory empty"
**Solution:**
1. Check full build log:
   ```bash
   cat build.log | tail -100
   ```

2. Look in buildozer directory:
   ```bash
   find .buildozer -name "*.apk"
   find .buildozer -name "*.log" -exec tail -20 {} \;
   ```

3. Verify buildozer.spec `package.name`:
   ```bash
   grep "^package.name" buildozer.spec
   ```

---

## 🔍 Detailed Debugging

### Enable Verbose Logging
```bash
buildozer -v android debug
# Even more verbose:
buildozer -vv android debug
```

### Check Build Logs
```bash
# Gradle logs
cat .buildozer/android/platform/build/build/outputs/logs/*.log

# Full buildozer logs
cat .buildozer/logs/python-for-android.log

# View all logs
find .buildozer -name "*.log" -type f | xargs tail -50
```

### Validate buildozer.spec
```bash
# Check syntax
cat buildozer.spec

# Find missing required fields
grep "^#\|^=" buildozer.spec | head -20
```

### Test Individual Components
```bash
# Test Python imports
python3 -c "import kivy; print(kivy.__version__)"
python3 -c "import requests; print(requests.__version__)"

# Test main.py syntax
python3 -m py_compile main.py

# Run app on desktop (if possible)
python3 main.py
```

---

## 🌐 GitHub Actions Debugging

### View Full Workflow Logs
1. Go to: `https://github.com/sk4153645-ux/kivy-app/actions`
2. Click on the failed workflow run
3. Expand each step to see detailed output

### Download Artifacts
- **BuildLogs**: Contains all .log files from the build
- **BuildReport**: Contains BUILD_REPORT.md with summary
- **NilgiriDairy-APK**: The generated APK (if successful)

### Re-run Failed Workflow
1. Go to failed workflow
2. Click "Re-run failed jobs" (top right)
3. Fix issues locally first before re-running

---

## 📊 Expected Build Times

| Stage | Time |
|-------|------|
| Setup dependencies | 5-10 min |
| Download NDK | 10-30 min (first time) |
| Download SDK | 5-15 min (first time) |
| Gradle build | 10-20 min |
| APK generation | 5-10 min |
| **Total (first build)** | **60-90 min** |
| **Total (cached)** | **20-40 min** |

---

## 📁 Important Directories

```
.buildozer/                    # Build cache
├── android/
│   ├── platform/
│   │   ├── build/             # Gradle build
│   │   ├── build-*_api*/      # API-specific builds
│   │   └── ...
│   └── ...
├── logs/                       # Buildozer logs
└── ...

~/.buildozer/                  # Global buildozer cache
~/.gradle/caches/              # Gradle cache
~/Android/Sdk/                 # Android SDK (if installed)
```

---

## 🧹 Clean Commands

```bash
# Clean current build
buildozer android clean

# Clean everything
buildozer android cleanall

# Remove project .buildozer
rm -rf .buildozer

# Remove global cache
rm -rf ~/.buildozer
rm -rf ~/.gradle

# Remove old APKs
rm -rf bin/*

# Full reset (WARNING: will redownload everything)
rm -rf .buildozer ~/.buildozer ~/.gradle bin
```

---

## ✅ Success Indicators

When build succeeds, you should see:
1. ✅ "build completed successfully" message
2. ✅ APK file in `bin/` directory
3. ✅ File name like `nilgiridairy-1.0.0-debug.apk`
4. ✅ File size typically 50-150MB

```bash
# Verify APK
ls -lh bin/*.apk
file bin/*.apk
```

---

## 🆘 Still Having Issues?

1. **Check the detailed build logs:**
   ```bash
   find .buildozer -name "*.log" -type f | xargs grep -i "error" | head -20
   ```

2. **Look for this specific errors:**
   - "compilation failed"
   - "download failed"
   - "permission denied"
   - "out of space"

3. **Provide this info when asking for help:**
   - Python version: `python3 --version`
   - Java version: `java -version`
   - Buildozer version: `buildozer --version`
   - Full build output: `buildozer -v android debug 2>&1 | tee build.log`
   - buildozer.spec content
   - OS and available disk space

---

## 📞 Resources

- **Buildozer Docs:** https://buildozer.readthedocs.io/
- **Kivy Docs:** https://kivy.org/doc/stable/
- **Python-for-Android:** https://python-for-android.readthedocs.io/
- **GitHub Actions:** https://docs.github.com/en/actions

---

**Last Updated:** 2026-08-28  
**App:** Nilgiri Dairy App v1.0.0  
**Built with:** Buildozer 1.5.0, Kivy 2.3.0
