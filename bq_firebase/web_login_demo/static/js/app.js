/**
 * @fileoverview Firebase and Google Analytics initialization and event
 * tracking for web login demo application.
 */

let firebaseConfig = null;
let ga4Config = null;

/**
 * Loads configuration from backend API.
 *
 * @return {Promise<?Object>} Configuration object or null on error.
 */
async function loadConfig() {
  try {
    const response = await fetch('/api/config');
    const config = await response.json();
    firebaseConfig = config.firebase;
    ga4Config = config.ga4;
    return config;
  } catch (error) {
    console.error('Error loading configuration:', error);
    return null;
  }
}

/**
 * Initializes Google Analytics 4.
 *
 * Loads the gtag.js script and configures GA4 with the measurement ID
 * from the loaded configuration.
 */
function initGA4() {
  if (!ga4Config || !ga4Config.measurementId) {
    console.warn('GA4 Measurement ID not configured');
    return;
  }

  const script = document.createElement('script');
  script.async = true;
  script.src =
    `https://www.googletagmanager.com/gtag/js?id=${ga4Config.measurementId}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer || [];
  /**
   * Global gtag function for Google Analytics.
   */
  function gtag() {
    dataLayer.push(arguments);
  }
  window.gtag = gtag;

  gtag('js', new Date());
  gtag('config', ga4Config.measurementId, {
    send_page_view: true
  });

  console.log('Google Analytics 4 initialized');
}

/**
 * Tracks a custom analytics event.
 *
 * @param {string} eventName The name of the event to track.
 * @param {Object=} eventParams Optional parameters for the event.
 */
function trackEvent(eventName, eventParams = {}) {
  if (window.gtag) {
    window.gtag('event', eventName, eventParams);
    console.log(`Event tracked: ${eventName}`, eventParams);
  } else {
    console.warn('GA4 not initialized, event not tracked:', eventName);
  }
}

// Login page functionality
if (document.getElementById('loginButton')) {
  loadConfig().then((config) => {
    if (config) {
      initGA4();

      trackEvent('page_view', {
        page_title: 'Login Page',
        page_location: window.location.href
      });

      const loginButton = document.getElementById('loginButton');
      loginButton.addEventListener('click', () => {
        trackEvent('login_initiated', {
          method: 'google'
        });

        window.location.href = '/auth/google';
      });
    }
  });
}

// Success page functionality
if (document.getElementById('userInfo')) {
  loadConfig().then((config) => {
    if (config) {
      initGA4();

      trackEvent('page_view', {
        page_title: 'Success Page',
        page_location: window.location.href
      });

      trackEvent('login_success', {
        method: 'google'
      });

      loadUserInfo();
    }
  });
}

/**
 * Loads and displays user information from the backend API.
 *
 * Fetches user profile and YouTube channel data, updates the DOM with
 * the retrieved information, and tracks analytics events.
 */
async function loadUserInfo() {
  const loadingState = document.getElementById('loadingState');
  const userInfo = document.getElementById('userInfo');
  const errorState = document.getElementById('errorState');

  try {
    const response = await fetch('/api/user-info');
    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    loadingState.style.display = 'none';
    userInfo.style.display = 'block';

    document.getElementById('userPhoto').src = data.user.picture;
    document.getElementById('userName').textContent = data.user.name;
    document.getElementById('userEmail').textContent = data.user.email;
    document.getElementById('userId').textContent = data.user.id;
    document.getElementById('emailVerified').textContent =
      data.user.verified_email ? 'Yes' : 'No';

    trackEvent('user_profile_loaded', {
      user_id: data.user.id,
      email_verified: data.user.verified_email
    });

    const youtubeData = document.getElementById('youtubeData');

    if (data.youtube && !data.youtube.error) {
      const youtube = data.youtube;
      youtubeData.innerHTML = `
        <div class="youtube-channel">
          <img src="${youtube.thumbnail}" alt="Channel thumbnail"
               class="channel-thumbnail">
          <div class="channel-info">
            <h4>${youtube.channelTitle}</h4>
            <p class="channel-id">Channel ID: ${youtube.channelId}</p>
          </div>
        </div>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">Subscribers:</span>
            <span class="value">${formatNumber(youtube.subscriberCount)}</span>
          </div>
          <div class="data-item">
            <span class="label">Total Videos:</span>
            <span class="value">${formatNumber(youtube.videoCount)}</span>
          </div>
          <div class="data-item">
            <span class="label">Total Views:</span>
            <span class="value">${formatNumber(youtube.viewCount)}</span>
          </div>
          <div class="data-item">
            <span class="label">Created:</span>
            <span class="value">${formatDate(youtube.publishedAt)}</span>
          </div>
        </div>
        ${youtube.description ?
          `<p class="channel-description">${youtube.description}</p>` : ''}
      `;

      document.getElementById('youtubeEvent').style.display = 'flex';

      trackEvent('youtube_data_collected', {
        channel_id: youtube.channelId,
        subscriber_count: parseInt(youtube.subscriberCount),
        video_count: parseInt(youtube.videoCount),
        view_count: parseInt(youtube.viewCount)
      });
    } else {
      youtubeData.innerHTML = `
        <div class="info-message">
          <p>No YouTube channel found or access was not granted.</p>
          <p class="small">You may not have a YouTube channel associated
             with this account.</p>
        </div>
      `;
    }
  } catch (error) {
    console.error('Error loading user info:', error);
    loadingState.style.display = 'none';
    errorState.style.display = 'block';

    trackEvent('error', {
      error_message: error.message,
      error_location: 'user_info_load'
    });
  }
}

/**
 * Formats a number with locale-specific thousands separators.
 *
 * @param {string|number} num The number to format.
 * @return {string} Formatted number string.
 */
function formatNumber(num) {
  return parseInt(num).toLocaleString();
}

/**
 * Formats a date string into a human-readable format.
 *
 * @param {string} dateString ISO date string to format.
 * @return {string} Formatted date string (e.g., "January 1, 2024").
 */
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}
