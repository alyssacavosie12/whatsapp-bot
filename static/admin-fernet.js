(() => {
  "use strict";

  const decoder = new TextDecoder();

  function base64UrlToBytes(value) {
    let normalized = value.trim().replace(/-/g, "+").replace(/_/g, "/");
    while (normalized.length % 4) {
      normalized += "=";
    }

    const binary = atob(normalized);
    const bytes = new Uint8Array(binary.length);

    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }

    return bytes;
  }

  function constantTimeEqual(left, right) {
    if (left.length !== right.length) {
      return false;
    }

    let diff = 0;
    for (let index = 0; index < left.length; index += 1) {
      diff |= left[index] ^ right[index];
    }

    return diff === 0;
  }

  async function importFernetKeys(keyText) {
    const keyBytes = base64UrlToBytes(keyText);

    if (keyBytes.length !== 32) {
      throw new Error("Fernet key must decode to 32 bytes");
    }

    const signingKey = keyBytes.slice(0, 16);
    const encryptionKey = keyBytes.slice(16, 32);

    return {
      signingKey: await crypto.subtle.importKey(
        "raw",
        signingKey,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"],
      ),
      encryptionKey: await crypto.subtle.importKey(
        "raw",
        encryptionKey,
        { name: "AES-CBC" },
        false,
        ["decrypt"],
      ),
    };
  }

  async function decryptFernetToken(tokenText, keyText) {
    const keys = await importFernetKeys(keyText);
    const token = base64UrlToBytes(tokenText);

    if (token.length < 1 + 8 + 16 + 1 + 32) {
      throw new Error("Fernet token is too short");
    }

    if (token[0] !== 0x80) {
      throw new Error("Unsupported Fernet token version");
    }

    const signedPayload = token.slice(0, token.length - 32);
    const expectedMac = token.slice(token.length - 32);
    const actualMac = new Uint8Array(
      await crypto.subtle.sign("HMAC", keys.signingKey, signedPayload),
    );

    if (!constantTimeEqual(expectedMac, actualMac)) {
      throw new Error("Invalid Fernet signature");
    }

    const iv = token.slice(9, 25);
    const ciphertext = token.slice(25, token.length - 32);
    const plaintext = new Uint8Array(
      await crypto.subtle.decrypt(
        { name: "AES-CBC", iv },
        keys.encryptionKey,
        ciphertext,
      ),
    );

    return decoder.decode(plaintext);
  }

  function getKeyInput() {
    return document.querySelector("[data-fernet-key]");
  }

  function getCurrentKey() {
    const input = getKeyInput();
    if (!input) {
      return "";
    }

    const typedKey = input.value.trim();
    if (typedKey) {
      sessionStorage.setItem("adminFernetKey", typedKey);
      return typedKey;
    }

    return sessionStorage.getItem("adminFernetKey") || "";
  }

  function setStatus(text, isError = false) {
    const status = document.querySelector("[data-decrypt-status]");
    if (!status) {
      return;
    }

    status.textContent = text;
    status.hidden = false;
    status.dataset.error = isError ? "true" : "false";
  }

  async function decryptElement(element) {
    const key = getCurrentKey();
    if (!key) {
      setStatus("Enter the Fernet key first. The key stays in this browser tab.", true);
      return;
    }

    const token = element.dataset.fernetToken || "";
    const output = element.querySelector("[data-decrypted-output]");

    if (!token || !output) {
      return;
    }

    try {
      const plaintext = await decryptFernetToken(token, key);
      output.textContent = plaintext;
      output.hidden = false;
      element.dataset.decrypted = "true";
      setStatus("Message decrypted locally in your browser.");
    } catch (error) {
      output.textContent = "Decrypt failed. Check the Fernet key.";
      output.hidden = false;
      setStatus("Decrypt failed. Check the Fernet key.", true);
    }
  }

  async function decryptAll() {
    const encryptedElements = Array.from(document.querySelectorAll("[data-fernet-token]"));
    if (!encryptedElements.length) {
      setStatus("No encrypted messages on this page.");
      return;
    }

    for (const element of encryptedElements) {
      await decryptElement(element);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const input = getKeyInput();
    const savedKey = sessionStorage.getItem("adminFernetKey");

    if (input && savedKey) {
      input.value = savedKey;
    }

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }

      const decryptOne = target.closest("[data-decrypt-one]");
      if (decryptOne) {
        const encryptedElement = decryptOne.closest("[data-fernet-token]");
        if (encryptedElement instanceof HTMLElement) {
          void decryptElement(encryptedElement);
        }
        return;
      }

      if (target.closest("[data-decrypt-all]")) {
        void decryptAll();
      }

      if (target.closest("[data-forget-fernet-key]")) {
        sessionStorage.removeItem("adminFernetKey");
        const keyInput = getKeyInput();
        if (keyInput) {
          keyInput.value = "";
        }
        setStatus("Fernet key removed from this browser tab.");
      }
    });
  });
})();
