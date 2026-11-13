> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/integrations/opencode.md).

# How to Run Local AI Models with OpenCode

Guide to connect open LLMs with OpenCode on your local device.

This guide walks you through connecting **OpenCode** to [Unsloth](https://github.com/unslothai/unsloth) to run open LLMs **entirely locally.** OpenCode is an **open-source AI coding agent** that reads, modifies, and executes code across your project using a connected model. This works with any **local model** exposed through Unsloth’s **OpenAI-compatible API**, including: DeepSeek, Qwen, Gemma, and more.

OpenCode acts as the client, while Unsloth loads and serves models via a local API. After setup, OpenCode connects to Unsloth, where you can select a loaded model and use it as a **coding agent**.

This guide covers both setup options:

* **OpenCode Desktop:** add Unsloth Studio manually as a custom OpenAI-compatible provider.
* **OpenCode CLI:** launch it with `unsloth start opencode` and connect to your local model automatically.

<a href="https://unsloth.ai/docs/integrations/opencode#installing-opencode-desktop" class="button primary">OpenCode Setup</a><a href="/docs/integrations/opencode.md#quickstart" class="button primary">Quickstart</a>

{% hint style="info" %}
In this tutorial, we’ll use `unsloth/Qwen3.6-27B-GGUF` loaded in Unsloth and access it directly inside OpenCode. Prefer a different model? Swap in any other model by loading it in Unsloth.
{% endhint %}

### Installing OpenCode Desktop

{% tabs %}
{% tab title="MacOS" %}

#### **Step 1: Download the OpenCode installer for Mac**

Open `opencode.ai/download` in your browser of choice. Scroll down to the **OpenCode Desktop (Beta) ,** and click the `Download` button next to the macOS image name corresponding to your Mac's architecture (Apple Silicon or Intel).

#### Step 2: Install OpenCode

Locate and double click the `OpenCode Desktop.dmg` installer file in your downloads folder.

The installer window will open. Use your mouse to drag the **OpenCode** app icon on top of the **Applications** icon as shown.

#### Step 3: Launch OpenCode

Locate and double click the **OpenCode** icon under the **Applications** folder.

The **OpenCode** desktop app will open and is now ready for your next action.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FZNP4G1c2hmHyBzNbGH5x%2Fopencode_interface.png?alt=media&amp;token=5af679cb-504d-4299-a40e-0d8310289a90" alt="" width="563"><figcaption></figcaption></figure></div>
{% endtab %}

{% tab title="Windows" %}

#### **Step 1: Download the OpenCode installer for Windows**

Open `opencode.ai/download` in your browser. Scroll to **OpenCode Desktop (Beta)**, and click the **Download** button next to the Windows (x64) installer.

#### **Step 2: Install OpenCode**

find the `OpenCode Desktop Installer.exe` in your Downloads folder and double click it. You can then follow the prompts in the installer window to complete the installation.

#### **Step 3: Launch OpenCode**

Open the Windows Start menu and search for **OpenCode**.\
\
Click the OpenCode app icon to launch it. The OpenCode desktop app will open and is now ready for your next action

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FLECAvpw6DMNCcuFclzoy%2Fimage.png?alt=media&amp;token=7a628b56-3e0c-4d00-8054-ab8b9317e4f9" alt="" width="563"><figcaption></figcaption></figure></div>
{% endtab %}

{% tab title="Linux" %}

#### **Step 1: Download the OpenCode installer for Linux**

Go to `opencode.ai/download` using your preferred web browser. Find the **OpenCode Desktop (Beta)** section, then choose the Linux download option for your system.

#### **Step 2: Install OpenCode**

Open your Downloads folder and find the **OpenCode** installer you just downloaded.

For an AppImage download, right click the file, open **Properties**, and enable the option that allows the file to run as a program. Then double click the AppImage to start **OpenCode**.

Or, if you prefer using the terminal, run:

```
chmod +x OpenCode*.AppImage
./OpenCode*.AppImage
```

If you downloaded a `.deb` file, install it with:

```
sudo apt install ./OpenCode*.deb
```

If you downloaded an `.rpm` file, install it with:

```
sudo dnf install ./OpenCode*.rpm
```

#### **Step 3: Launch OpenCode**

Open your Linux application launcher and search for **OpenCode**.

Click the OpenCode app icon to launch it. The OpenCode desktop app will open and is now ready for your next action.
{% endtab %}
{% endtabs %}

### ⚡ Quickstart

After installing OpenCode, we'll need to install [Unsloth Desktop](/docs/desktop.md) to enable OpenCode to serve and run inference of local models.

{% stepper %}
{% step %}

#### Download Unsloth

The easiest way to get started is by installing the Unsloth Desktop app. It supports [MacOS](/docs/get-started/install/mac.md), Linux, [Windows](/docs/get-started/install/windows-installation.md), [NVIDIA](/docs/get-started/install/pip-install.md), [AMD](/docs/get-started/install/amd.md), Intel and CPU setups.

<a href="https://unsloth.ai/download" class="button primary" data-icon="down-to-bracket">Download Unsloth</a>

* <i class="fa-apple">:apple:</i> [Download for macOS](https://unsloth.ai/download/mac)
* <i class="fa-windows">:windows:</i> [Download for Windows](https://unsloth.ai/download/windows)
* <i class="fa-linux">:linux:</i> [Download for Linux](https://unsloth.ai/download/linux)

Or, if you prefer manual installation:

**MacOS, Linux, WSL:**

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

**Windows PowerShell:**

```bash
irm https://unsloth.ai/install.ps1 | iex
```

{% endstep %}

{% step %}

#### Install

1. Open the Unsloth installer (`.dmg`, `.exe` files)
2. Drag Unsloth to Applications for Mac or complete setup for Windows.
3. Launch the app and wait for installation to complete
   {% endstep %}

{% step %}

#### Choose a model

Open 'Select model' dropdown ontop or 'Model hub' tab, choose a model and a quantization that fits your device, then download it. Once it finishes, start chatting - no setup required.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FNCEVgKLJI0goPqjgcg9B%2Fmodel%20hub%20models.png?alt=media&amp;token=533b5e3c-a901-4b33-963e-4a703cc9d5a6" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}

### Unsloth is now ready

To start chatting, type a message and press Enter.

**Connect OpenCode.** Run `unsloth start opencode`. It mints an API key, writes the config, and launches OpenCode against your loaded model.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FpAGvwjGD0iVMZKBoyu7m%2Fgreeennn.png?alt=media&amp;token=d17a5528-8375-444c-9aff-f9e9f7903bcd" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}
{% endstepper %}

### 🔑 Creating an API key

1. Open the sidebar, click your **Unsloth** avatar at the bottom-left.
2. Go to **Settings** → **API**.
3. Enter a friendly name (e.g. `claude-code-macbook`).
4. *(Optional)* Set an expiry.
5. Click **Create**.
6. **Copy the key immediately.** Unsloth stores only a hash and you won't be able to view it again.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FrWnqY5PgvZdbWK8pmlD5%2Fimage.png?alt=media&amp;token=3507e7d7-b552-447f-b503-2418802b8f6e" alt="" width="375"><figcaption></figcaption></figure>

All keys start with the `sk-unsloth-` prefix. Revoke a key from the same page at any time. Requests made with a revoked key will fail with `401 Unauthorized`.

## 🖇️ Connecting Unsloth to OpenCode Desktop

**Opencode** supports any OpenAI-compatible provider, so you can wire Unsloth in as a **Custom** provider. The setup is a one-time flow inside opencode's **Connect provider** dialog.

**1. Open the provider picker.** In opencode, type `/model` (or click the model selector at the bottom of the input).

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fl59D1AVRI57fQBJqgp8t%2Fslash-model.png?alt=media&amp;token=9434f804-6a9e-4b76-ab7e-75cd745fe9c2" alt="" width="563"><figcaption></figcaption></figure></div>

Then click **Connect provider** at the top-right of the select model dialog.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fi9VOd4yRAmLnqZ1D4tBm%2Fconnect%20provider.png?alt=media&amp;token=cb28387a-9cc3-4c5f-928e-82a56edd86df" alt="" width="375"><figcaption></figcaption></figure></div>

**2. Choose "Custom".** In the provider list, scroll to **Other** and pick **Custom**.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FWyltmg0o9YtyydUSLvcn%2Fcustom%20highlighted.png?alt=media&amp;token=5cc89686-dfae-4ebd-8beb-e6dc78088b4b" alt="" width="375"><figcaption></figcaption></figure></div>

**3. Fill in the custom provider form:**

| Field            | Value                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| **Provider ID**  | `unsloth-studio` *(lowercase, hyphens allowed)*                                                   |
| **Display name** | `Unsloth Studio`                                                                                  |
| **Base URL**     | `http://localhost:8888/v1/` *(replace `8888` with your* Unsloth *port; keep the trailing `/v1/`)* |
| **API key**      | Your `sk-unsloth-…` key                                                                           |

In the **Models** section, add one row per model you want to expose. The left field is the model ID as Unsloth serves it; the right field is what opencode will display:

| Model ID (left)                                                                | Display name (right)                                 |
| ------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `unsloth/Qwen3.6-27B-GGUF` *(the exact name of the model as shown in Unsloth)* | `unsloth/Qwen3.6-27B-GGUF` *(shown inside opencode)* |

Leave **Headers** empty unless you're proxying Unsloth through an auth layer that needs custom headers.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FjGU2OaOKRtqCwmO34BuN%2Fopencode_custom_provider_config.png?alt=media&amp;token=6ef67ecf-23e6-4913-bc02-c26701f5aea0" alt="" width="375"><figcaption></figcaption></figure></div>

**4. Click Submit.** You should see an *"Unsloth Studio connected. Unsloth models are now available to use"* toast.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FuCOOOJhO8brhEwwIsiUC%2Fopencode_model_available_toast.png?alt=media&amp;token=a463bb0c-724a-4809-9ddb-b7bff094b255" alt="" width="375"><figcaption></figcaption></figure>

{% hint style="warning" %}
**Restart opencode after adding the provider.** The new provider only becomes selectable after a restart.
{% endhint %}

**5. Select your Unsloth model.** Once opencode is back up, type `/model`, search `unsloth`, and pick the model under the **Unsloth Studio** group. It'll be active on your next message.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FFRNofXnF7r7CKlHjLMwv%2Fopencode_unsloth_model_usage.png?alt=media&amp;token=4c882e8f-6ac5-4f9b-8f59-5e86e312851b" alt="" width="375"><figcaption></figcaption></figure></div>

Unsloth supports both OpenAI and Anthropic python SDKs.

### ⚙️ **OpenCode CLI**

OpenCode CLI can connect to a model already running in Unsloth Studio, or start one automatically when Unsloth is not running.

#### If Unsloth Studio is already running

With a model loaded in Unsloth Studio, open your project folder and run:

```bash
unsloth start opencode
```

Using this command launches OpenCode with the model currently loaded in Unsloth, without changing your existing OpenCode setup.

#### Start a model automatically

If Unsloth isn't already running, you can launch a temporary server and load a model in a single command:

To launch OpenCode directly with a model, run:

```bash
unsloth start opencode \
    --model unsloth/Qwen3.8-27B-GGUF-GGUF:UD-Q4_K_XL
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.0 \
    --reasoning-effort medium
```

Unsloth automatically selects the correct parameters to use but you can still change it.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fom5iWH1f42GZ69utVSyf%2Fimage.png?alt=media&amp;token=815a0458-b252-4c96-a341-e345842bd248" alt="" width="563"><figcaption></figcaption></figure></div>

Once **OpenCode** opens, give it a task such as:

```
Create a Flash-style Python 2D game with jumping, dashing, and two levels.
```

It can inspect the project, create files, edit code, and run commands using the local model.

<div align="center" data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FOA6dENYOpJdGa3zwS8Ei%2Fimage.png?alt=media&amp;token=266a85f8-ec80-4a7d-bd58-e82d9ff0b864" alt="" width="563"><figcaption></figcaption></figure></div>

In this example, the model created a two-level platformer. Let’s open it up and see how it turned out.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FHqFv9FyPsM0poo5c6WNb%2Fezgif-68bd7a9b463725d0.gif?alt=media&amp;token=abafdfef-6e13-430b-bccb-140f29ee6d13" alt="" width="563"><figcaption></figcaption></figure></div>

#### Resume your work

OpenCode keeps your session history automatically, so you do not need `--persist`. To pick up where you left off, even if Unsloth is no longer running, use:

```bash
unsloth start opencode \
  --model unsloth/Qwen3.6-27B-GGUF \
  --continue
```

To open a particular session instead, use `--session <session-id>`.

See the complete [unsloth start](/docs/integrations/unsloth-start.md) reference for model loading, remote Unsloth servers, and advanced options.

### Optional: configure server access

`unsloth run` starts the local API server and loads a model for OpenCode to connect to. You can also customize how the server behaves when starting it.

```bash
# Run the API on port 8888 (--disable-tools passes OpenCode's own tools through)
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF \
  --disable-tools \
  -p 8888
```

{% hint style="warning" %}
Use `--disable-tools` when driving OpenCode (or any external coding agent). By default Unsloth Studio runs its own server-side tools, which swallows the agent's tool calls, so OpenCode answers but never edits files. `--disable-tools` switches to passthrough, so OpenCode's own tools are used.
{% endhint %}

Use `-p` to change which port the server runs on.

```bash
# Allow other devices on your network to connect
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF \
  -H 0.0.0.0 \
  --disable-tools \
  -p 8888
```

This starts the server on `0.0.0.0:8888`, allowing other devices on your local network to connect.

For more advanced runtime configuration, see the main [API tuning](https://unsloth.ai/docs/basics/api#unsloth-run-command) section.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/integrations/opencode.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
