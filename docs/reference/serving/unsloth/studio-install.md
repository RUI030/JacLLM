> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/new/studio/install.md).

# Unsloth Studio Installation

Manually install Unsloth Studio, or download the separate Unsloth Desktop app.

Unsloth Studio works on Windows, Linux, WSL and MacOS. You should use the same installation process on every device, although the system requirements may differ by device.

### Install with Unsloth Desktop

The easiest way to install Unsloth Studio is with the native [Desktop app](/docs/desktop.md). Download it for your operating system:

* <i class="fa-apple">:apple:</i> [Download for macOS](https://unsloth.ai/download/mac)
* <i class="fa-windows">:windows:</i> [Download for Windows](https://unsloth.ai/download/windows)
* <i class="fa-linux">:linux:</i> [Download for Linux](https://unsloth.ai/download/linux)

The rest of this page installs **Unsloth Studio** manually.

### Manual Unsloth Studio installation

<a href="https://unsloth.ai/docs/new/studio/install#windows-1" class="button secondary" data-icon="windows">Windows</a><a href="https://unsloth.ai/docs/new/studio/install#macos-1" class="button secondary" data-icon="apple">MacOS</a><a href="https://unsloth.ai/docs/new/studio/install#linux-and-wsl" class="button secondary medium" data-icon="linux">Linux & WSL</a><a href="/docs/new/studio/install.md#docker" class="button secondary" data-icon="docker">Docker</a><a href="https://unsloth.ai/docs/new/studio/install#developer-nightly-installations-advanced" class="button secondary" data-icon="screwdriver-wrench">Developer Install</a>

### Quickstart

{% tabs %}
{% tab title="MacOS, Linux, WSL" %}
**Install Unsloth:**

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

Use the same command to update.
{% endtab %}

{% tab title="Windows" %}
**Install Unsloth:**

```powershell
irm https://unsloth.ai/install.ps1 | iex
```

Use the same command to update.
{% endtab %}

{% tab title="Docker" %}
The [Unsloth Docker image](https://hub.docker.com/r/unsloth/unsloth) `unsloth/unsloth` is available on Docker. [Read guide.](https://unsloth.ai/docs/get-started/install/docker)
{% endtab %}

{% tab title="Homebrew" %}
Install Unsloth Desktop:

{% code collapsedlinecount="10" %}

```bash
brew install --cask unsloth
```

{% endcode %}

Update Unsloth Desktop:

```bash
brew upgrade --cask unsloth
```

{% endtab %}

{% tab title="WinGet" %}
Install Unsloth Desktop:

```powershell
winget install --id UnslothAI.Unsloth -e
```

Update Unsloth Desktop:

```powershell
winget upgrade --id UnslothAI.Unsloth -e
```

{% endtab %}
{% endtabs %}

See below for more step-by-step instructions:

{% tabs %}
{% tab title="MacOS" %}

#### Step 1: Setup Unsloth

Launch the `terminal` from Mac, then install Unsloth by entering the command below.

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

or use **Homebrew**:

```bash
brew install --cask unsloth
```

Unsloth will start setting up the environment and installing the required packages as shown below. Type **Y** and Press `Enter` when asked if you want to allow Unsloth to start now. This will start Unsloth on your local **8888** port.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FnKjv9Qn86NpTc0jIAANL%2FStart_studio_windows_powershell.png?alt=media&amp;token=be7dfb36-80a9-4a5d-bcf6-063a887a471e" alt="" width="375"><figcaption></figcaption></figure>

{% hint style="info" %}
If you chose not to start Unsloth during the installation process, you can always start the Unsloth app using `unsloth studio -p 8888` . If you would like to have your Unsloth instance accessible by clients outside of your PC/computer, add `-H 0.0.0.0` to the `unsloth studio` command.
{% endhint %}

#### Step 2: Start Unsloth

Open your browser of choice and go to the `http://127.0.0.1:8888` URL. If this is your first time installing Unsloth, you will be prompted to create a new password. After, the Unsloth app should now open on the Chat Page as shown below.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FNX8VzAre3aWM86uUz9U6%2Fimage.png?alt=media&amp;token=7eccde46-6188-48a5-95de-05f0e8bf44be" alt="" width="375"><figcaption></figcaption></figure>

**Launch Unsloth securely with HTTPS and Cloudflare.** Unsloth now provides a secure way to launch Unsloth over HTTPS through a free Cloudflare tunnel. Use the below (works in Windows, Mac & Linux):

```bash
unsloth studio --secure
```

You can start training and running models immediately. You can view our more detailed step-by-step guide to get started below:

{% content-ref url="/pages/vrLQd9559vRkDY8zRR0h" %}
[Get Started](/docs/new/studio/start.md)
{% endcontent-ref %}
{% endtab %}

{% tab title="Windows" %}

#### Step 1: Setup Unsloth

Open the Start Menu, search for `PowerShell`, and launch it. Copy & paste the install command below:

```powershell
irm https://unsloth.ai/install.ps1 | iex
```

it will begin installing automatically. After installation finishes, PowerShell will ask if you want to start Unsloth Studi&#x6F;**.**

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FnKjv9Qn86NpTc0jIAANL%2FStart_studio_windows_powershell.png?alt=media&amp;token=be7dfb36-80a9-4a5d-bcf6-063a887a471e" alt="" width="375"><figcaption></figcaption></figure>

You can also launch it with the following command:

```bash
unsloth studio -H 0.0.0.0 -p 8888
```

{% hint style="info" %}
If you would like to have your instance accessible by clients outside of your PC/computer.\
Add `-H 0.0.0.0` to the `unsloth studio` command.
{% endhint %}

#### Step 2: Start Unsloth

Open `http://127.0.0.1:8888` in your browser. On first launch, create a new password to continue to the Chat page. **Unsloth Studio** is now installed and ready to use.

The Unsloth app should now open on the Chat Page as shown below.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FtQZliTMxnBZcJSAidbOc%2Fimage.png?alt=media&amp;token=df1e9734-b7ba-448d-b600-1025035527ca" alt="" width="375"><figcaption></figcaption></figure>

**Launch Unsloth securely with HTTPS and Cloudflare.** Unsloth now provides a secure way to launch Unsloth over HTTPS through a free Cloudflare tunnel. Use the below (works in Windows, Mac & Linux):

```bash
unsloth studio --secure
```

You can start training and  running models immediately. You can view our more detailed step-by-step guide to get started below:

{% content-ref url="/pages/vrLQd9559vRkDY8zRR0h" %}
[Get Started](/docs/new/studio/start.md)
{% endcontent-ref %}
{% endtab %}

{% tab title="Linux, WSL" %}

#### Step 1: Setup Unsloth

{% tabs %}
{% tab title="Linux" %}
Open your terminal application. You can launch it by pressing `Ctrl + Alt + T`, or by searching for `Terminal` in your system's application menu.
{% endtab %}

{% tab title="WSL" %}
Click the Windows Start Menu, type the name of your installed distro (e.g. `Ubuntu`), then open it.

{% hint style="warning" %}
On **WSL**, make sure your **NVIDIA drivers** are installed on **Windows** (not inside WSL) and that the **CUDA toolkit** is installed inside your WSL distro. See the System Requirements below for details.
{% endhint %}
{% endtab %}
{% endtabs %}

To install, copy and run the install command:

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

Then:

1. Click inside the terminal window
2. Paste the command with `Ctrl + Shift + V`
3. Press `Enter`

Unsloth will start setting up the environment and installing the required packages as shown below. Type **Y** and Press `Enter` when asked if you want to allow Unsloth to start now. This will start Unsloth on your local **8888** port.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FaCUj9vIsSLtxrrRZ4UVx%2Fimage.png?alt=media&amp;token=27f413dd-65b2-4312-b344-506919bccc6c" alt=""><figcaption></figcaption></figure>

{% hint style="info" %}
If you chose not to start Unsloth during the installation process, you can always start the Unsloth app using `unsloth studio -p 8888` . If you would like to have your Unsloth instance accessible by clients outside of your PC/computer, add `-H 0.0.0.0` to the `unsloth studio` command.
{% endhint %}

#### Step 2: Start Unsloth

Open your browser of choice and type `http://127.0.0.1:8888` in the URL box. If this is your first time installing Unsloth, you will be forwarded to `http://127.0.0.1:8888/change-password` page as shown below:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FnM9s9317lNmCQVJugLDU%2Fimage.png?alt=media&amp;token=740cb99d-23ab-4767-bfa2-41f49769d96d" alt="" width="563"><figcaption></figcaption></figure>

**Launch Unsloth securely with HTTPS and Cloudflare.** Unsloth now provides a secure way to launch Unsloth over HTTPS through a free Cloudflare tunnel. Use the below (works in Windows, Mac & Linux):

```bash
unsloth studio --secure
```

You can start training and  running models immediately. You can view our more detailed step-by-step guide to get started below:

{% content-ref url="/pages/vrLQd9559vRkDY8zRR0h" %}
[Get Started](/docs/new/studio/start.md)
{% endcontent-ref %}
{% endtab %}
{% endtabs %}

## System Requirements

### <i class="fa-windows">:windows:</i> Window**s**

Unsloth Studio works directly on Windows without WSL. To train models, make sure your system satisfies these requirements:

**Requirements**

* Windows 10 or Windows 11 (64-bit)
* NVIDIA GPU with drivers installed (for Intel GPUs, see [Intel GPUs](#intel-gpus))
* **App Installer** (includes `winget`): [here](https://learn.microsoft.com/en-us/windows/msix/app-installer/install-update-app-installer)
* **Git**: `winget install --id Git.Git -e --source winget`
* **Python**: version 3.11 up to, but not including, 3.14
* Work inside a Python environment such as **uv**, **venv**, or **conda/mamba**

### <i class="fa-apple">:apple:</i> MacOS

Unsloth Studio works on Mac devices for [Chat](#run-models-locally) and training and all features. You can run MLX models with Unsloth.

* macOS 12 Monterey or newer (Intel or Apple Silicon)
* Work inside a Python environment such as **uv**, **venv**, or **conda/mamba**

### <i class="fa-linux">:linux:</i> Linux & WSL

* Ubuntu 20.04+ or similar distro (64-bit)
* NVIDIA GPU with drivers installed (for Intel GPUs, see [Intel GPUs](#intel-gpus))
* CUDA toolkit (12.4+ recommended, 12.8+ for blackwell)
* Git: `sudo apt install git`
* Python: version 3.11 up to, but not including, 3.14
* Work inside a Python environment such as **uv**, **venv**, or **conda/mamba**

### <i class="fa-microchip">:microchip:</i> Intel GPUs

Install the latest Intel GPU driver first (see our [Intel guide](/docs/get-started/install/intel.md)). The installer then picks Intel XPU PyTorch by itself on Linux and Windows when an Intel Arc, Arc Pro, Core Ultra with Arc graphics, or Data Center GPU Max / Flex is the only GPU it finds. On Linux the installer's GPU line shows `Intel GPU (<device id>, XPU)` when this happens.

Pin XPU PyTorch yourself when the installer cannot see or pick the Intel GPU:

* **WSL**, where no PCI display device is visible to the installer
* a system that also has an NVIDIA or AMD GPU (one PyTorch install serves one vendor, so the other GPU will not be used for training)
* on Linux, `ONEAPI_DEVICE_SELECTOR`, `SYCL_DEVICE_FILTER` or `SYCL_DEVICE_ALLOWLIST` is set, or `ZE_AFFINITY_MASK` is set to anything other than empty or `default`

**Linux, WSL:**

{% code collapsedlinecount="10" %}

```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_TORCH_INDEX_FAMILY=xpu sh

# or with the full index URL
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_TORCH_INDEX_URL=https://download.pytorch.org/whl/xpu sh
```

{% endcode %}

**Windows (PowerShell):**

{% code collapsedlinecount="10" %}

```powershell
$env:UNSLOTH_TORCH_INDEX_FAMILY = "xpu"; irm https://unsloth.ai/install.ps1 | iex
```

{% endcode %}

If you pinned XPU (for example on WSL), set the same variable every time you re-run the installer to update; without it the re-run installs CPU PyTorch again. To keep CPU PyTorch on a system with an Intel GPU, set `UNSLOTH_TORCH_INDEX_FAMILY=cpu` instead (or `UNSLOTH_DISABLE_XPU_AUTO=1` on Linux).

### <i class="fa-docker">:docker:</i> Docker

{% hint style="success" %}
Our Docker image now works for Unsloth! We're working on Mac compatibility.
{% endhint %}

* Pull our latest Unsloth container image: `docker pull unsloth/unsloth`
* Run the container via:

```bash
docker run -d -e JUPYTER_PASSWORD="mypassword" \
  -p 8888:8888 -p 8000:8000 -p 2222:22 \
  -v $(pwd)/work:/workspace/work \
  --gpus all \
  unsloth/unsloth
```

For more information, [see here](https://hub.docker.com/r/unsloth/unsloth#unsloth-docker-image).

* Access your studio instance at `http://localhost:8000` or external ip address `http://external_ip_address:8000/`

### <i class="fa-microchip">:microchip:</i> CPU only

Unsloth Studio supports CPU devices for [Chat](#run-models-locally) for GGUF models and [Data Recipes](/docs/new/studio/data-recipe.md)

* Same as the ones mentioned above for Linux (except for NVIDIA GPU drivers) and MacOS.

## Developer / Nightly Installations (Advanced)

### **Main Repo Install**

#### **macOS, Linux, WSL developer installs:**

```bash
git clone https://github.com/unslothai/unsloth
cd unsloth
./install.sh --local
unsloth studio -p 8888
```

To install into an isolated location (its own virtual env, `auth/`, `studio.db`, cache and llama.cpp build), set `UNSLOTH_STUDIO_HOME` and pass it again at launch:

```bash
UNSLOTH_STUDIO_HOME="$PWD/.studio" ./install.sh --local
UNSLOTH_STUDIO_HOME="$PWD/.studio" unsloth studio -p 8888
```

Then to update :

```bash
cd unsloth && git pull
./install.sh --local
unsloth studio -p 8888
```

#### **Windows PowerShell developer installs:**

```powershell
git clone https://github.com/unslothai/unsloth.git
cd unsloth
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1 --local
unsloth studio -p 8888
```

To install into an isolated location (its own virtual env, `auth/`, `studio.db`, cache and llama.cpp build), set `UNSLOTH_STUDIO_HOME` and pass it again at launch:

```powershell
$env:UNSLOTH_STUDIO_HOME="$PWD\.studio"; .\install.ps1 --local
$env:UNSLOTH_STUDIO_HOME="$PWD\.studio"; unsloth studio -p 8888
```

Then to update :

```powershell
cd unsloth; git pull
.\install.ps1 --local
unsloth studio -p 8888
```

#### **Remote access: `--secure` (HTTPS tunnel) vs raw port**

By default `unsloth studio` binds to `127.0.0.1` (this machine only). To reach it from another device, pick one of:

* `--secure` (recommended): serve **only** through a free Cloudflare HTTPS link. Unsloth stays bound to localhost and the tunnel provides the public URL; it fails closed (does not start) if the tunnel can't come up, so the raw port is never exposed.

```bash
unsloth studio --secure -p 8888
```

* `-H 0.0.0.0`: bind the raw port on all network interfaces, reachable from anywhere on the network. Only use this on a trusted network.

```bash
unsloth studio -H 0.0.0.0 -p 8888
```

Server-side tools (web search, Python and terminal code execution) run as your user and are on by default. Anyone who can reach the server with the API key can run code on this machine, so keep your API key private and pass `--disable-tools` when exposing Unsloth.

### Advanced Launch methods

Installer options can be passed as environment variables. On macOS, Linux and WSL place the variable after the pipe so the shell passes it to `sh`; on Windows set it with `$env:` before piping to `iex`.

Skip PyTorch (GGUF-only mode):

```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_NO_TORCH=1 sh
```

```powershell
$env:UNSLOTH_NO_TORCH=1; irm https://unsloth.ai/install.ps1 | iex
```

Pin the Python version:

```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_PYTHON=3.12 sh
```

```powershell
$env:UNSLOTH_PYTHON='3.12'; irm https://unsloth.ai/install.ps1 | iex
```

Install to a custom location with `UNSLOTH_STUDIO_HOME`:

```bash
curl -fsSL https://unsloth.ai/install.sh | UNSLOTH_STUDIO_HOME=/abs/path sh
```

```powershell
$env:UNSLOTH_STUDIO_HOME='C:\path'; irm https://unsloth.ai/install.ps1 | iex
```

Cap Unsloth's native CPU thread pools on high-core hosts: `UNSLOTH_CPU_THREADS=8 unsloth studio -p 8888`.

### **Use an Old Version**

#### **Unsloth Desktop**

To use an old version of Unsloth Desktop, it is very simple. Just look through [our GitHub releases](https://github.com/unslothai/unsloth/releases) and select the specific release you want to install in the 'Assets' area.

#### **Unsloth Studio**

To use an old version of Unsloth Studio, follow the below with your desired version and names:

**macOS, Linux, WSL:**

```shellscript
uv pip install \
  --python "$HOME/.unsloth/studio/unsloth_studio/bin/python" \
  --reinstall --no-deps "unsloth==VERSION"

"$HOME/.unsloth/studio/unsloth_studio/bin/unsloth" studio -p 8888
```

**Windows:**

```shellscript
uv pip install `
  --python "$env:USERPROFILE\.unsloth\studio\unsloth_studio\Scripts\python.exe" `
  --reinstall --no-deps "unsloth==VERSION"

& "$env:USERPROFILE\.unsloth\studio\unsloth_studio\Scripts\unsloth.exe" studio -p 8888
```

### Uninstall

The recommended way to fully remove Unsloth Studio is the matching uninstall script for your OS. It stops any running servers, removes the install dir, the launcher data dir, the desktop shortcut, and any platform-specific entries (macOS `.app` bundle + Launch Services on Mac; Start Menu, `HKCU\Software\Unsloth` registry key and user `PATH` entries on Windows):

* ​ **MacOS, WSL, Linux:**

{% code overflow="wrap" expandable="true" %}

```bash
curl -fsSL https://raw.githubusercontent.com/unslothai/unsloth/main/scripts/uninstall.sh | sh
```

{% endcode %}

* ​ **Windows (PowerShell):**

{% code overflow="wrap" expandable="true" %}

```bash
 irm https://raw.githubusercontent.com/unslothai/unsloth/main/scripts/uninstall.ps1 | iex
```

{% endcode %}

If you only want to drop the install dir and keep the launcher/shortcut for a later reinstall, you can instead run `rm -rf ~/.unsloth/studio` (Mac/Linux/WSL) or `Remove-Item -Recurse -Force "$HOME\.unsloth\studio"` (Windows). The model cache at `~/.cache/huggingface` is not touched by any of these.

#### Manual uninstall

If you prefer to remove only specific parts:

**1. Remove app only** (keeps history, chats, checkpoints, and exports intact):

* **macOS, WSL, Linux:** `rm -rf ~/.unsloth/studio/unsloth_studio`
* **Windows (PowerShell):** `Remove-Item -Recurse -Force "$HOME\.unsloth\studio\unsloth_studio"`

**2. Remove Unsloth entirely** (keeps other Unsloth tools intact):

* **macOS, WSL, Linux:** `rm -rf ~/.unsloth/studio`
* **Windows (PowerShell):** `Remove-Item -Recurse -Force "$HOME\.unsloth\studio"`

**3. Remove everything Unsloth-related:**

* **macOS, WSL, Linux:** `rm -rf ~/.unsloth`
* **Windows (PowerShell):** `Remove-Item -Recurse -Force "$HOME\.unsloth"`

{% hint style="warning" %}
Note: Step 3 deletes everything in history, chats, model checkpoints, and exports. This cannot be undone.
{% endhint %}

**4. Remove shortcuts and symlinks:**

**macOS:**

```shellscript
rm -rf ~/Applications/Unsloth\ Studio.app ~/Desktop/Unsloth\ Studio
```

**Linux:**&#x20;

```shellscript
rm -f ~/.local/share/applications/unsloth-studio.desktop ~/Desktop/unsloth-studio.desktop
```

**WSL / Windows (PowerShell):**

```shellscript
Remove-Item -Force "$HOME\Desktop\Unsloth Studio.lnk"
Remove-Item -Force "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Unsloth Studio.lnk"
```

**5. Remove the CLI command:**

* **macOS, Linux, WSL:** `rm -f ~/.local/bin/unsloth`
* **Windows (PowerShell):** The installer added the venv's `Scripts` directory to your User PATH. To remove it, open Settings → System → About → Advanced system settings → Environment Variables, find `Path` under User variables, and remove the entry pointing to `.unsloth\studio\...\Scripts`.

{% hint style="info" %}
Note: Steps 1-5 dont touch your downloaded HF model files. See Deleting cached HF model files below if you want to reclaim that space.
{% endhint %}

### **Deleting cached HF model files**

You can delete old model files either from the bin icon in model search or by removing the relevant cached model folder from the default Hugging Face cache directory. By default, Hugging Face uses `~/.cache/huggingface/hub/` on macOS/Linux/WSL and `C:\Users\<username>\.cache\huggingface\hub\` on Windows.

* **MacOS, Linux, WSL:** `~/.cache/huggingface/hub/`
* **Windows:** `%USERPROFILE%\.cache\huggingface\hub\`

If `HF_HUB_CACHE` or `HF_HOME` is set, use that location instead. On Linux and WSL, `XDG_CACHE_HOME` can also change the default cache root.

### Using old / existing GGUF models

{% columns %}
{% column %}
**Apr 1 update:** You can now select an existing folder for Unsloth to detect from.

**Mar 27 update:** Unsloth Studio now **automatically detects older / pre-existing models** downloaded from Hugging Face, LM Studio etc.
{% endcolumn %}

{% column %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FBn3Fs1cchFchl328wSOs%2FScreenshot%202026-04-05%20at%205.43.57%E2%80%AFAM.png?alt=media&amp;token=cc57ec6e-653a-4824-8e8d-a6bfbcd27493" alt=""><figcaption></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

**Manual instructions:** Unsloth Studio detects models downloaded to your Hugging Face Hub cache `(C:\Users{your_username}.cache\huggingface\hub)`. If you have GGUF models downloaded through LM Studio, note that these are stored in `C:\Users{your_username}.cache\lm-studio\models` ***OR*** `C:\Users{your_username}\lm-studio\models` . Sometimes when they are not visible, you will need to move or copy those .gguf files into your Hugging Face Hub cache directory (or another path accessible to llama.cpp) for Unsloth Studio to load them.

After fine-tuning a model or adapter in Unsloth, you can export it to GGUF and run local inference with **llama.cpp** directly in Unsloth Chat. Unsloth Studio is powered by llama.cpp and Hugging Face.

### <i class="fa-google">:google:</i> Google Colab notebook

We’ve created a [free Google Colab notebook](https://colab.research.google.com/github/unslothai/unsloth/blob/main/studio/Unsloth_Studio_Colab.ipynb) so you can explore all of Unsloth’s features on Colab’s T4 GPUs. You can train and run most models up to 22B parameters, and switch to a larger GPU for bigger models. Just Click 'Run all' and the UI should pop up after installation.

{% columns %}
{% column %}
{% embed url="<https://colab.research.google.com/github/unslothai/unsloth/blob/main/studio/Unsloth_Studio_Colab.ipynb>" %}

Once installation is complete, scroll to **Start Unsloth Studio** and click **Open Unsloth Studio** in the white box shown on the left:

**Scroll further down, to see the actual UI.**
{% endcolumn %}

{% column %}

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FkYitMrK55Ic6eIGqiKEJ%2FScreenshot%202026-03-16%20at%2011.21.16%E2%80%AFPM.png?alt=media&amp;token=4388c309-a598-41f3-9301-e434c334ac1c" alt=""><figcaption></figcaption></figure></div>
{% endcolumn %}
{% endcolumns %}

{% hint style="warning" %}
Sometimes the Unsloth link may return an error. This happens because you might have disabled cookies or you're using an adblocker or Mozilla. You can still access the UI by scrolling below the button.

Google Colab also expects you to stay on the Colab page; if it detects inactivity, it may shut down the GPU session.
{% endhint %}

## Troubleshooting

<table><thead><tr><th width="211.5999755859375">Problem</th><th>Fix</th></tr></thead><tbody><tr><td>Python version error</td><td><code>sudo apt install python3.12 python3.12-venv</code> version 3.11 up to, but not including, 3.14</td></tr><tr><td><code>nvidia-smi not found</code></td><td>Install NVIDIA drivers from https://www.nvidia.com/Download/index.aspx</td></tr><tr><td><code>nvcc not found</code> (CUDA)</td><td><code>sudo apt install nvidia-cuda-toolkit</code> or add <code>/usr/local/cuda/bin</code> to PATH</td></tr><tr><td>llama-server build failed</td><td>Non-fatal, Unsloth still works, GGUF inference won't be available. Install <code>cmake</code> and re-run setup to fix.</td></tr><tr><td><code>cmake not found</code></td><td><code>sudo apt install cmake</code></td></tr><tr><td><code>git not found</code></td><td><code>sudo apt install git</code></td></tr><tr><td>Build failed</td><td>Delete <code>~/.unsloth/llama.cpp</code> and re-run setup</td></tr></tbody></table>


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/new/studio/install.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
