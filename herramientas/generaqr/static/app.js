(() => {
  const form = document.querySelector('#qr-form');
  if (!form) return;

  const photoFile = document.querySelector('#photo-file');
  const photoCamera = document.querySelector('#photo-camera');
  const photoPreviewWrap = document.querySelector('#photo-preview-wrap');
  const photoPreview = document.querySelector('#photo-preview');
  const photoStatus = document.querySelector('#photo-status');
  const removePhoto = document.querySelector('#remove-photo');
  const customCheck = document.querySelector('input[name="style"][value="personalizado"]');
  const customWrap = document.querySelector('#custom-shape-wrap');
  const customInput = document.querySelector('#custom-shape');
  const color = document.querySelector('#qr-color');
  const colorValue = document.querySelector('#color-value');
  const button = document.querySelector('#submit-button');
  const formError = document.querySelector('#form-error');
  const modal = document.querySelector('#result-modal');
  const resultImage = document.querySelector('#result-image');
  const resultUrl = document.querySelector('#result-url');
  const downloadButton = document.querySelector('#download-button');
  const modalAd = document.querySelector('#modal-ad');
  const closeAd = document.querySelector('#close-ad');

  let photoPreviewUrl = null;
  let qrObjectUrl = null;

  const clearError = () => {
    formError.hidden = true;
    formError.textContent = '';
  };

  const showError = (message) => {
    formError.textContent = message;
    formError.hidden = false;
    formError.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const clearPhoto = () => {
    photoFile.value = '';
    photoCamera.value = '';
    photoPreviewWrap.hidden = true;
    photoPreview.removeAttribute('src');
    photoStatus.textContent = 'Foto seleccionada';
    if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
    photoPreviewUrl = null;
  };

  const selectPhoto = (activeInput, otherInput) => {
    const file = activeInput.files[0];
    if (!file) return;
    otherInput.value = '';
    if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
    photoPreviewUrl = URL.createObjectURL(file);
    photoPreview.src = photoPreviewUrl;
    photoStatus.textContent = file.name || 'Fotografía tomada';
    photoPreviewWrap.hidden = false;
    clearError();
  };

  photoFile.addEventListener('change', () => selectPhoto(photoFile, photoCamera));
  photoCamera.addEventListener('change', () => selectPhoto(photoCamera, photoFile));
  removePhoto.addEventListener('click', clearPhoto);

  const syncCustom = () => {
    const selected = form.querySelector('input[name="style"]:checked');
    const isCustom = selected?.value === 'personalizado';
    customWrap.hidden = !isCustom;
    customInput.required = isCustom;
  };
  form.querySelectorAll('input[name="style"]').forEach((input) => {
    input.addEventListener('change', syncCustom);
  });
  syncCustom();

  color.addEventListener('input', () => {
    colorValue.value = color.value.toUpperCase();
  });

  const setWorking = (working) => {
    button.disabled = working;
    button.querySelector('.button-label').hidden = working;
    button.querySelector('.button-working').hidden = !working;
  };

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add('modal-open');
    modalAd.hidden = false;
    document.querySelector('.modal-close').focus();
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    if (qrObjectUrl) URL.revokeObjectURL(qrObjectUrl);
    qrObjectUrl = null;
    resultImage.removeAttribute('src');
    downloadButton.removeAttribute('href');
    form.reset();
    clearPhoto();
    syncCustom();
    colorValue.value = '#000000';
    clearError();
    document.querySelector('#website-url').focus();
  };

  document.querySelectorAll('[data-close-modal]').forEach((control) => {
    control.addEventListener('click', closeModal);
  });
  closeAd.addEventListener('click', () => {
    modalAd.hidden = true;
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) closeModal();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError();

    if (!photoFile.files.length && !photoCamera.files.length) {
      showError('Selecciona una fotografía o toma una con la cámara.');
      return;
    }

    setWorking(true);
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'image/png, application/json' },
      });

      if (!response.ok) {
        let message = 'No fue posible generar el QR.';
        try {
          const payload = await response.json();
          if (payload.error) message = payload.error;
        } catch (_error) {
          // Se conserva el mensaje general cuando el servidor no devuelve JSON.
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      qrObjectUrl = URL.createObjectURL(blob);
      const filename = response.headers.get('X-QR-Filename') || 'mi_codigo_QR.png';
      const websiteHeader = response.headers.get('X-QR-Website');
      let website = form.website_url.value;
      if (websiteHeader) {
        try {
          website = decodeURI(websiteHeader);
        } catch (_error) {
          website = websiteHeader;
        }
      }

      resultImage.src = qrObjectUrl;
      resultUrl.textContent = website;
      downloadButton.href = qrObjectUrl;
      downloadButton.download = filename;
      openModal();
    } catch (error) {
      showError(error.message || 'No fue posible generar el QR. Inténtalo de nuevo.');
    } finally {
      setWorking(false);
    }
  });
})();
