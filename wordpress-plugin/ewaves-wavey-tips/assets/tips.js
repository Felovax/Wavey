/* E-Waves Wavey-tips – opptak og innsending fra mobil */
(function () {
  'use strict';

  var root = document.getElementById('wavey-tips');
  if (!root) return;

  var MAX_SECONDS = 60;
  var TARGET_RATE = 16000; // 16 kHz mono holder godt for tale

  var cfg = window.WaveyTips || {};
  var params = new URLSearchParams(window.location.search);
  var eventId = cfg.arrangement || (params.get('arrangement') || '').toLowerCase();

  var recBtn = document.getElementById('wt-rec');
  var timerEl = document.getElementById('wt-timer');
  var preview = document.getElementById('wt-preview');
  var textEl = document.getElementById('wt-text');
  var consentEl = document.getElementById('wt-consent');
  var sendBtn = document.getElementById('wt-send');
  var msgEl = document.getElementById('wt-msg');

  var mediaRecorder = null, chunks = [], wavBlob = null, timerId = null, seconds = 0;

  if (!/^[a-z0-9-]{3,60}$/.test(eventId)) {
    showMsg('Denne lenken mangler arrangement. Scan QR-koden på nytt.', true);
    recBtn.disabled = true;
    return;
  }

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    recBtn.hidden = true;
    timerEl.textContent = 'Opptak støttes ikke i denne nettleseren – skriv tipset under.';
  }

  function updateSendState() {
    var hasContent = wavBlob || textEl.value.trim().length >= 10;
    sendBtn.disabled = !(hasContent && consentEl.checked);
  }
  textEl.addEventListener('input', updateSendState);
  consentEl.addEventListener('change', updateSendState);

  recBtn.addEventListener('click', function () {
    if (mediaRecorder && mediaRecorder.state === 'recording') { stopRecording(); return; }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      chunks = []; wavBlob = null; preview.hidden = true; showMsg('');
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
      mediaRecorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        var recorded = new Blob(chunks, { type: mediaRecorder.mimeType });
        toWav(recorded).then(function (wav) {           // webm (Chrome) / mp4 (Safari) -> WAV
          wavBlob = wav;
          preview.src = URL.createObjectURL(wav);
          preview.hidden = false;
          updateSendState();
        }).catch(function () {
          showMsg('Kunne ikke behandle opptaket. Prøv igjen eller skriv tipset.', true);
        });
      };
      mediaRecorder.start();
      recBtn.classList.add('is-recording'); recBtn.textContent = 'Stopp';
      seconds = 0; tick();
      timerId = setInterval(tick, 1000);
    }).catch(function () {
      showMsg('Fikk ikke tilgang til mikrofonen. Du kan skrive tipset i stedet.', true);
    });
  });

  function tick() {
    timerEl.textContent = seconds + ' / ' + MAX_SECONDS + ' sek';
    if (seconds >= MAX_SECONDS) stopRecording();
    seconds++;
  }

  function stopRecording() {
    clearInterval(timerId);
    if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
    recBtn.classList.remove('is-recording'); recBtn.textContent = 'Ta opp på nytt';
  }

  // Dekoder opptaket og lager en 16 kHz mono WAV-fil (formatet Gemini støtter fra alle telefoner)
  function toWav(blob) {
    var Ctx = window.AudioContext || window.webkitAudioContext;
    var ctx = new Ctx();
    return blob.arrayBuffer().then(function (buf) {
      return new Promise(function (resolve, reject) { ctx.decodeAudioData(buf, resolve, reject); });
    }).then(function (decoded) {
      ctx.close();
      var offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * TARGET_RATE), TARGET_RATE);
      var src = offline.createBufferSource();
      src.buffer = decoded; src.connect(offline.destination); src.start();
      return offline.startRendering();
    }).then(function (rendered) {
      var samples = rendered.getChannelData(0);
      var buffer = new ArrayBuffer(44 + samples.length * 2);
      var view = new DataView(buffer);
      function writeStr(o, s) { for (var i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); }
      writeStr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); writeStr(8, 'WAVE');
      writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
      view.setUint32(24, TARGET_RATE, true); view.setUint32(28, TARGET_RATE * 2, true);
      view.setUint16(32, 2, true); view.setUint16(34, 16, true);
      writeStr(36, 'data'); view.setUint32(40, samples.length * 2, true);
      for (var i = 0, o = 44; i < samples.length; i++, o += 2) {
        var s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
      return new Blob([view], { type: 'audio/wav' });
    });
  }

  sendBtn.addEventListener('click', function () {
    sendBtn.disabled = true; showMsg('Sender …');
    var form = new FormData();
    form.append('event_id', eventId);
    form.append('consent', consentEl.checked ? 'true' : 'false');
    if (wavBlob) form.append('audio', wavBlob, 'tips.wav');
    else form.append('text', textEl.value.trim());

    fetch(cfg.submitUrl, { method: 'POST', body: form, credentials: 'omit' })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) throw new Error(data.error || 'Noe gikk galt. Prøv igjen.');
          document.getElementById('wt-form').hidden = true;
          document.getElementById('wt-done').hidden = false;
        });
      })
      .catch(function (err) { showMsg(err.message, true); updateSendState(); });
  });

  function showMsg(text, isError) {
    msgEl.textContent = text;
    msgEl.className = 'wt-msg' + (isError ? ' is-error' : '');
  }
})();
