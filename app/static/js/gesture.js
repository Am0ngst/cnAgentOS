var GestureSystem = (function() {
    'use strict';

    var STATE_STOPPED = 'stopped';
    var STATE_LOADING = 'loading';
    var STATE_RUNNING = 'running';
    var STATE_PAUSED = 'paused';

    var GESTURE_NAMES = {
        OPEN_PALM: 'open_palm',
        INDEX_UP: 'index_up',
        INDEX_MIDDLE_UP: 'index_middle_up',
        OK: 'ok',
        FIST: 'fist',
        PINKY_OUT: 'pinky_out'
    };

    var GESTURE_LABELS = {};
    GESTURE_LABELS[GESTURE_NAMES.OPEN_PALM] = '手掌张开';
    GESTURE_LABELS[GESTURE_NAMES.INDEX_UP] = '食指竖起 (1)';
    GESTURE_LABELS[GESTURE_NAMES.INDEX_MIDDLE_UP] = '食中指竖起 (2)';
    GESTURE_LABELS[GESTURE_NAMES.OK] = 'OK 确认';
    GESTURE_LABELS[GESTURE_NAMES.FIST] = '握拳';
    GESTURE_LABELS[GESTURE_NAMES.PINKY_OUT] = '小指伸出';

    var DEBOUNCE_MS = 1000;
    var DETECTION_ZONE_RATIO = 0.70;

    var hands = null;
    var cameraInstance = null;
    var videoElement = null;
    var canvasElement = null;
    var canvasCtx = null;
    var currentState = STATE_STOPPED;
    var lastGesture = null;
    var lastGestureTime = 0;
    var stableGesture = null;
    var stableGestureCount = 0;
    var stableGestureThreshold = 10;
    var currentGestureLabel = '无手势';
    var actionCallbacks = {};
    var pageContext = 'home';
    var guideShown = false;
    var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    var detectionStarted = false;
    var debugCounter = 0;
    var handDetectedLogged = false;
    var lastResultsTime = 0;
    var healthCheckTimer = null;
    var frameTimer = null;
    var lastProcessTime = 0;
    var FRAME_INTERVAL_MS = 50;

    var overlayEl = null;
    var guideEl = null;
    var cameraRequestEl = null;
    var toggleEl = null;
    var toastTimer = null;

    function init() {
        if (currentState !== STATE_STOPPED) return;
        currentState = STATE_LOADING;
        createOverlay();
        showCameraRequest(function(granted) {
            if (granted) {
                loadMediaPipe();
            } else {
                currentState = STATE_STOPPED;
                destroyOverlay();
                showToast('摄像头权限被拒绝，手势交互无法启动');
            }
        });
    }

    function createOverlay() {
        if (overlayEl) return;

        overlayEl = document.createElement('div');
        overlayEl.id = 'gesture-overlay';
        overlayEl.innerHTML =
            '<div id="gesture-status-bar">' +
                '<span id="gesture-indicator-dot"></span>' +
                '<span id="gesture-label">就绪中...</span>' +
                '<button id="gesture-toggle-btn" title="关闭手势交互">✕</button>' +
            '</div>' +
            '<div id="gesture-camera-container">' +
                '<video id="gesture-video" playsinline autoplay></video>' +
                '<canvas id="gesture-canvas"></canvas>' +
            '</div>';
        overlayEl.style.cssText =
            'position:fixed;z-index:99990;top:80px;right:16px;pointer-events:auto;';

        document.body.appendChild(overlayEl);

        document.getElementById('gesture-status-bar').style.cssText =
            'display:flex;align-items:center;gap:8px;padding:6px 12px;' +
            'background:rgba(0,0,0,0.85);border-radius:12px 12px 0 0;' +
            'backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);' +
            'border-bottom:none;';

        document.getElementById('gesture-indicator-dot').style.cssText =
            'width:8px;height:8px;border-radius:50%;background:#22c55e;' +
            'animation:pulse-dot 1.5s infinite;flex-shrink:0;';

        document.getElementById('gesture-label').style.cssText =
            'color:#fff;font-size:12px;font-weight:500;white-space:nowrap;';

        document.getElementById('gesture-toggle-btn').style.cssText =
            'background:none;border:none;color:rgba(255,255,255,0.5);cursor:pointer;' +
            'font-size:14px;padding:0 4px;line-height:1;';

        document.getElementById('gesture-camera-container').style.cssText =
            'position:relative;width:200px;height:150px;' +
            'background:#000;border-radius:0 0 12px 12px;' +
            'overflow:hidden;border:1px solid rgba(255,255,255,0.1);border-top:none;';

        var pulseStyle = document.createElement('style');
        pulseStyle.textContent =
            '@keyframes pulse-dot {0%,100%{opacity:1}50%{opacity:0.4}}' +
            '#gesture-camera-container video{width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}' +
            '#gesture-camera-container canvas{position:absolute;top:0;left:0;width:100%;height:100%;transform:scaleX(-1)}';
        document.head.appendChild(pulseStyle);

        document.getElementById('gesture-toggle-btn').addEventListener('click', function(e) {
            e.stopPropagation();
            stop();
        });

        document.getElementById('gesture-status-bar').addEventListener('click', function() {
            var container = document.getElementById('gesture-camera-container');
            container.style.display = container.style.display === 'none' ? 'block' : 'none';
        });

        videoElement = document.getElementById('gesture-video');
        canvasElement = document.getElementById('gesture-canvas');
        if (canvasElement) {
            canvasCtx = canvasElement.getContext('2d');
        }
    }

    function destroyOverlay() {
        if (overlayEl && overlayEl.parentNode) {
            overlayEl.parentNode.removeChild(overlayEl);
        }
        overlayEl = null;
        videoElement = null;
        canvasElement = null;
        canvasCtx = null;
    }

    function showCameraRequest(callback) {
        if (cameraRequestEl) {
            if (cameraRequestEl.parentNode) {
                cameraRequestEl.parentNode.removeChild(cameraRequestEl);
            }
        }

        cameraRequestEl = document.createElement('div');
        cameraRequestEl.style.cssText =
            'position:fixed;top:0;left:0;right:0;bottom:0;' +
            'background:rgba(0,0,0,0.6);z-index:100000;' +
            'display:flex;align-items:center;justify-content:center;' +
            'backdrop-filter:blur(4px);';

        cameraRequestEl.innerHTML =
            '<div style="background:rgba(18,24,40,0.98);border-radius:20px;padding:40px 36px;' +
            'max-width:420px;width:90%;text-align:center;' +
            'border:1px solid rgba(255,255,255,0.1);box-shadow:0 20px 60px rgba(0,0,0,0.5);">' +
                '<div style="font-size:56px;margin-bottom:20px;">📷</div>' +
                '<h3 style="color:#fff;margin-bottom:12px;font-size:20px;">申请摄像头权限</h3>' +
                '<p style="color:rgba(255,255,255,0.5);font-size:14px;line-height:1.8;margin-bottom:28px;">' +
                    '手势交互功能需要使用摄像头来识别您的手势。<br>' +
                    '视频数据仅在本地处理，不会上传到服务器。' +
                '</p>' +
                '<div style="display:flex;gap:12px;">' +
                    '<button id="camera-deny-btn" style="flex:1;padding:12px;' +
                    'background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);' +
                    'border-radius:12px;color:rgba(255,255,255,0.6);font-size:14px;cursor:pointer;">拒绝</button>' +
                    '<button id="camera-allow-btn" style="flex:1;padding:12px;' +
                    'background:linear-gradient(135deg,#00d4ff,#a855f7);border:none;' +
                    'border-radius:12px;color:#fff;font-size:14px;font-weight:600;cursor:pointer;">允许</button>' +
                '</div>' +
            '</div>';

        document.body.appendChild(cameraRequestEl);

        document.getElementById('camera-allow-btn').addEventListener('click', function() {
            if (cameraRequestEl && cameraRequestEl.parentNode) {
                cameraRequestEl.parentNode.removeChild(cameraRequestEl);
            }
            cameraRequestEl = null;
            callback(true);
        });

        document.getElementById('camera-deny-btn').addEventListener('click', function() {
            if (cameraRequestEl && cameraRequestEl.parentNode) {
                cameraRequestEl.parentNode.removeChild(cameraRequestEl);
            }
            cameraRequestEl = null;
            callback(false);
        });
    }

    function showGuide() {
        if (guideShown) return;
        if (guideEl) {
            if (guideEl.parentNode) guideEl.parentNode.removeChild(guideEl);
        }

        guideEl = document.createElement('div');
        guideEl.style.cssText =
            'position:fixed;top:0;left:0;right:0;bottom:0;' +
            'background:rgba(0,0,0,0.7);z-index:100001;' +
            'display:flex;align-items:center;justify-content:center;' +
            'backdrop-filter:blur(6px);';

        var gestureCards = [
            {icon: '🖐️', name: '手掌完全张开', action: '打开全局快捷菜单', color: '#00d4ff'},
            {icon: '☝️', name: '食指向上竖起', action: '切换到智能问数子系统', color: '#a855f7'},
            {icon: '✌️', name: '食中指向上竖起', action: '切换到智能聊天子系统', color: '#22c55e'},
            {icon: '👌', name: 'OK手势', action: '确认/发送当前消息', color: '#f59e0b'},
            {icon: '✊', name: '握拳', action: '返回上一级/关闭弹窗', color: '#ef4444'},
            {icon: '🤙', name: '小指伸出', action: '@数字员工/拉起快捷对话', color: '#ec4899'}
        ];

        guideEl.innerHTML =
            '<div style="background:rgba(18,24,40,0.98);border-radius:20px;padding:36px 32px;' +
            'max-width:600px;width:90%;max-height:85vh;overflow-y:auto;' +
            'border:1px solid rgba(255,255,255,0.1);box-shadow:0 20px 60px rgba(0,0,0,0.5);">' +
                '<h3 style="color:#fff;margin-bottom:6px;font-size:22px;text-align:center;">' +
                    '🖐️ 手势引导图</h3>' +
                '<p style="color:rgba(255,255,255,0.4);font-size:13px;text-align:center;margin-bottom:24px;">' +
                    '将手放在摄像头中央区域，做出以下手势即可操作</p>' +
                '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">' +
                    gestureCards.map(function(card) {
                        return '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);' +
                            'border-radius:14px;padding:16px 14px;display:flex;align-items:center;gap:14px;">' +
                            '<div style="width:48px;height:48px;border-radius:14px;' +
                            'background:' + card.color + '20;display:flex;align-items:center;justify-content:center;' +
                            'font-size:26px;flex-shrink:0;">' + card.icon + '</div>' +
                            '<div style="min-width:0;">' +
                                '<div style="color:#fff;font-size:13px;font-weight:600;margin-bottom:3px;">' + card.name + '</div>' +
                                '<div style="color:' + card.color + ';font-size:11px;">' + card.action + '</div>' +
                            '</div>' +
                        '</div>';
                    }).join('') +
                '</div>' +
                '<div style="margin-top:20px;padding:14px;background:rgba(0,212,255,0.06);' +
                'border-radius:12px;border:1px solid rgba(0,212,255,0.15);">' +
                    '<p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0;line-height:1.8;text-align:center;">' +
                        '💡 提示：手势识别区域为画面中央 70%，避免边缘误触<br>' +
                        '手势触发间隔 1 秒，持续保持手势以触发操作' +
                    '</p>' +
                '</div>' +
                '<div style="text-align:center;margin-top:20px;">' +
                    '<button id="guide-got-it-btn" style="padding:12px 48px;' +
                    'background:linear-gradient(135deg,#00d4ff,#a855f7);border:none;' +
                    'border-radius:12px;color:#fff;font-size:15px;font-weight:600;cursor:pointer;">' +
                    '我知道了</button>' +
                '</div>' +
            '</div>';

        document.body.appendChild(guideEl);

        document.getElementById('guide-got-it-btn').addEventListener('click', function() {
            if (guideEl && guideEl.parentNode) {
                guideEl.parentNode.removeChild(guideEl);
            }
            guideEl = null;
            guideShown = true;
            try {
                localStorage.setItem('gesture_guide_shown', '1');
            } catch(e) {}
        });
    }

    function loadMediaPipe() {
        updateStatus('加载手势模型...');

        var scriptsToLoad = [
            'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js',
            'https://cdn.jsdelivr.net/npm/@mediapipe/control_utils@0.6/control_utils.js',
            'https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js',
            'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js'
        ];

        var loaded = 0;
        var totalToLoad = scriptsToLoad.length;

        function onAllLoaded() {
            initHands();
        }

        scriptsToLoad.forEach(function(src) {
            if (document.querySelector('script[src="' + src + '"]')) {
                loaded++;
                if (loaded === totalToLoad) onAllLoaded();
                return;
            }
            var script = document.createElement('script');
            script.src = src;
            script.crossOrigin = 'anonymous';
            script.onload = function() {
                loaded++;
                if (loaded === totalToLoad) onAllLoaded();
            };
            script.onerror = function() {
                showToast('手势模型加载失败，请检查网络连接');
                currentState = STATE_STOPPED;
                destroyOverlay();
            };
            document.head.appendChild(script);
        });
    }

    function initHands() {
        try {
            hands = new window.Hands({
                locateFile: function(file) {
                    return 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/' + file;
                }
            });

            hands.setOptions({
                maxNumHands: 1,
                modelComplexity: isMobile ? 0 : 1,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.4
            });

            hands.onResults(onHandResults);
            startCamera();
        } catch(e) {
            showToast('手势模型初始化失败: ' + e.message);
            currentState = STATE_STOPPED;
            destroyOverlay();
        }
    }

    function startCamera() {
        if (!videoElement) {
            createOverlay();
        }

        var constraints = {
            video: {
                width: {ideal: 320},
                height: {ideal: 240},
                facingMode: 'user'
            }
        };

        navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
            videoElement.srcObject = stream;
            videoElement.addEventListener('loadeddata', function onLoadedData() {
                if (detectionStarted) return;
                if (canvasElement) {
                    canvasElement.width = videoElement.videoWidth;
                    canvasElement.height = videoElement.videoHeight;
                }
                startDetection();
            }, { once: true });
        }).catch(function(err) {
            showToast('无法访问摄像头: ' + (err.message || '权限不足'));
            currentState = STATE_STOPPED;
            destroyOverlay();
        });
    }

    function startDetection() {
        if (detectionStarted) return;
        if (!videoElement || !videoElement.videoWidth || !videoElement.videoHeight) {
            if (videoElement) {
                videoElement.addEventListener('loadeddata', function retryStart() {
                    if (detectionStarted) return;
                    if (videoElement.videoWidth && videoElement.videoHeight) {
                        if (canvasElement) {
                            canvasElement.width = videoElement.videoWidth;
                            canvasElement.height = videoElement.videoHeight;
                        }
                        _doStartDetection();
                    }
                }, { once: true });
            }
            return;
        }
        _doStartDetection();
    }

    function _doStartDetection() {
        if (detectionStarted) return;
        detectionStarted = true;
        currentState = STATE_RUNNING;
        updateStatus('手势识别中...');
        currentGestureLabel = '无手势';
        lastResultsTime = Date.now();
        lastProcessTime = 0;

        cameraInstance = new window.Camera(videoElement, {
            onFrame: function() {
                if (currentState !== STATE_RUNNING || !hands) return;
                var now = Date.now();
                if (now - lastProcessTime < FRAME_INTERVAL_MS) return;
                lastProcessTime = now;
                hands.send({image: videoElement});
            },
            width: videoElement.videoWidth || 320,
            height: videoElement.videoHeight || 240
        });
        cameraInstance.start();

        startHealthCheck();

        try {
            var shown = localStorage.getItem('gesture_guide_shown');
            if (!shown) {
                setTimeout(function() { showGuide(); }, 500);
            } else {
                guideShown = true;
            }
        } catch(e) {
            setTimeout(function() { showGuide(); }, 500);
        }

        showToast('手势交互已启动 ✓');
    }

    function startHealthCheck() {
        if (healthCheckTimer) clearInterval(healthCheckTimer);
        healthCheckTimer = setInterval(function() {
            if (currentState !== STATE_RUNNING) return;
            var now = Date.now();
            if (now - lastResultsTime > 8000) {
                console.log('[Gesture] 健康检查：超时无检测，重启Camera...');
                restartCamera();
            }
            if (now - lastProcessTime > 120000) {
                console.log('[Gesture] 定時重启Camera保持穩定...');
                restartCamera();
            }
        }, 5000);
    }

    function stopHealthCheck() {
        if (healthCheckTimer) {
            clearInterval(healthCheckTimer);
            healthCheckTimer = null;
        }
    }

    function restartCamera() {
        if (currentState !== STATE_RUNNING) return;
        if (cameraInstance) {
            try { cameraInstance.stop(); } catch(e) {}
            cameraInstance = null;
        }
        lastProcessTime = 0;
        lastResultsTime = Date.now();
        var vw = videoElement.videoWidth || 320;
        var vh = videoElement.videoHeight || 240;
        cameraInstance = new window.Camera(videoElement, {
            onFrame: function() {
                if (currentState !== STATE_RUNNING || !hands) return;
                var now = Date.now();
                if (now - lastProcessTime < FRAME_INTERVAL_MS) return;
                lastProcessTime = now;
                hands.send({image: videoElement});
            },
            width: vw,
            height: vh
        });
        cameraInstance.start();
        console.log('[Gesture] Camera已重啟');
    }

    function onHandResults(results) {
        lastResultsTime = Date.now();

        if (canvasCtx && canvasElement) {
            canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
        }

        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            if (!handDetectedLogged) {
                handDetectedLogged = true;
                console.log('[Gesture] 检测到手部，开始手势分类...');
            }
            var landmarks = results.multiHandLandmarks[0];
            var handedness = results.multiHandedness[0];

            if (canvasCtx) {
                try {
                    window.drawConnectors(canvasCtx, landmarks, window.HAND_CONNECTIONS, {
                        color: '#00d4ff',
                        lineWidth: 1.5
                    });
                    window.drawLandmarks(canvasCtx, landmarks, {
                        color: handedness.label === 'Left' ? '#a855f7' : '#00d4ff',
                        lineWidth: 1,
                        radius: 2
                    });
                } catch(e) {}
            }

            if (isInDetectionZone(landmarks)) {
                var gesture = classifyGesture(landmarks, handedness);
                handleGestureStabilization(gesture);
            } else {
                stableGesture = null;
                stableGestureCount = 0;
                updateGestureLabel('边缘区域');
            }
        } else {
            stableGesture = null;
            stableGestureCount = 0;
            updateGestureLabel('无手势');
        }
    }

    function isInDetectionZone(landmarks) {
        var sumX = 0, sumY = 0, count = landmarks.length;
        for (var i = 0; i < count; i++) {
            sumX += landmarks[i].x;
            sumY += landmarks[i].y;
        }
        var centerX = sumX / count;
        var centerY = sumY / count;
        var margin = (1 - DETECTION_ZONE_RATIO) / 2;

        var xInZone = centerX >= margin && centerX <= (1 - margin);
        var yInZone = centerY >= margin && centerY <= (1 - margin);

        return xInZone && yInZone;
    }

    function classifyGesture(landmarks, handedness) {
        function pipAngle(mcpIdx, pipIdx, tipIdx) {
            var dxM = landmarks[mcpIdx].x - landmarks[pipIdx].x;
            var dyM = landmarks[mcpIdx].y - landmarks[pipIdx].y;
            var dzM = (landmarks[mcpIdx].z || 0) - (landmarks[pipIdx].z || 0);
            var dxT = landmarks[tipIdx].x - landmarks[pipIdx].x;
            var dyT = landmarks[tipIdx].y - landmarks[pipIdx].y;
            var dzT = (landmarks[tipIdx].z || 0) - (landmarks[pipIdx].z || 0);

            var dot = dxM * dxT + dyM * dyT + dzM * dzT;
            var magM = Math.sqrt(dxM * dxM + dyM * dyM + dzM * dzM);
            var magT = Math.sqrt(dxT * dxT + dyT * dyT + dzT * dzT);

            if (magM < 0.0001 || magT < 0.0001) return 0;
            var cosVal = dot / (magM * magT);
            cosVal = Math.max(-1, Math.min(1, cosVal));
            return Math.acos(cosVal);
        }

        function dist3d(a, b) {
            var dx = landmarks[a].x - landmarks[b].x;
            var dy = landmarks[a].y - landmarks[b].y;
            var dz = (landmarks[a].z || 0) - (landmarks[b].z || 0);
            return Math.sqrt(dx * dx + dy * dy + dz * dz);
        }

        function isFistByTipCluster() {
            var tips = [4, 8, 12, 16, 20];
            var sumX = 0, sumY = 0;
            for (var i = 0; i < tips.length; i++) {
                sumX += landmarks[tips[i]].x;
                sumY += landmarks[tips[i]].y;
            }
            var cx = sumX / tips.length;
            var cy = sumY / tips.length;
            var maxRadius = 0;
            for (var j = 0; j < tips.length; j++) {
                var d = Math.hypot(landmarks[tips[j]].x - cx, landmarks[tips[j]].y - cy);
                if (d > maxRadius) maxRadius = d;
            }
            return maxRadius < 0.12;
        }

        var EXTEND_THRESHOLD = 2.0;

        var indexAngle = pipAngle(5, 6, 8);
        var middleAngle = pipAngle(9, 10, 12);
        var ringAngle = pipAngle(13, 14, 16);
        var pinkyAngle = pipAngle(17, 18, 20);
        var thumbAngle = pipAngle(2, 3, 4);

        var indexUp = indexAngle > EXTEND_THRESHOLD;
        var middleUp = middleAngle > EXTEND_THRESHOLD;
        var ringUp = ringAngle > EXTEND_THRESHOLD;
        var pinkyUp = pinkyAngle > EXTEND_THRESHOLD;
        var thumbUp = thumbAngle > 2.0;

        var thumbIndexDist = dist3d(4, 8);
        var thumbNearIndexPip = dist3d(4, 6) < 0.14;

        if (indexUp && middleUp && ringUp && pinkyUp && thumbUp) {
            return GESTURE_NAMES.OPEN_PALM;
        }

        if (indexUp && !middleUp && !ringUp && !pinkyUp) {
            return GESTURE_NAMES.INDEX_UP;
        }

        if (indexUp && middleUp && !ringUp && !pinkyUp) {
            return GESTURE_NAMES.INDEX_MIDDLE_UP;
        }

        if (thumbIndexDist < 0.07 && ringUp && pinkyUp) {
            return GESTURE_NAMES.OK;
        }

        if (isFistByTipCluster()) {
            return GESTURE_NAMES.FIST;
        }

        var curledCount = (indexUp ? 0 : 1) + (middleUp ? 0 : 1) + (ringUp ? 0 : 1) + (pinkyUp ? 0 : 1);
        if (curledCount >= 4 && thumbNearIndexPip) {
            return GESTURE_NAMES.FIST;
        }

        if (pinkyUp && !indexUp && !middleUp && !ringUp) {
            return GESTURE_NAMES.PINKY_OUT;
        }

        debugCounter++;
        if (debugCounter % 30 === 0) {
            console.log('[Gesture] angles | idx=' + indexAngle.toFixed(2) +
                ' mid=' + middleAngle.toFixed(2) +
                ' rng=' + ringAngle.toFixed(2) +
                ' pnk=' + pinkyAngle.toFixed(2) +
                ' thb=' + thumbAngle.toFixed(2) +
                ' | ext: idx=' + indexUp + ' mid=' + middleUp +
                ' rng=' + ringUp + ' pnk=' + pinkyUp + ' thbUp=' + thumbUp +
                ' | cluster=' + isFistByTipCluster() +
                ' | thbNearIdx=' + thumbNearIndexPip +
                ' | thbIdxDist=' + thumbIndexDist.toFixed(3));
        }

        return null;
    }

    function handleGestureStabilization(gesture) {
        if (gesture === stableGesture) {
            stableGestureCount++;
            if (stableGestureCount >= stableGestureThreshold) {
                triggerGesture(gesture);
                stableGesture = null;
                stableGestureCount = 0;
            }
        } else if (gesture !== null) {
            stableGesture = gesture;
            stableGestureCount = 1;
        } else {
            stableGesture = null;
            stableGestureCount = 0;
        }

        if (gesture && GESTURE_LABELS[gesture]) {
            updateGestureLabel(GESTURE_LABELS[gesture]);
        } else if (gesture === null && stableGesture === null) {
            updateGestureLabel('无手势');
        }
    }

    function triggerGesture(gesture) {
        var now = Date.now();
        if (gesture === lastGesture && (now - lastGestureTime) < DEBOUNCE_MS) {
            return;
        }

        lastGesture = gesture;
        lastGestureTime = now;

        var label = GESTURE_LABELS[gesture] || gesture;
        showToast('识别手势：' + label);
        console.log('[GestureSystem] 触发手势:', label);

        if (actionCallbacks[gesture]) {
            var callbacks = actionCallbacks[gesture];
            if (typeof callbacks === 'function') {
                callbacks(pageContext);
            } else if (Array.isArray(callbacks)) {
                callbacks.forEach(function(cb) { cb(pageContext); });
            }
        }
    }

    function updateGestureLabel(label) {
        if (currentGestureLabel === label) return;
        currentGestureLabel = label;
        var labelEl = document.getElementById('gesture-label');
        if (labelEl) {
            labelEl.textContent = label;
        }
    }

    function updateStatus(status) {
        var labelEl = document.getElementById('gesture-label');
        if (labelEl) {
            labelEl.textContent = status;
        }
    }

    function showToast(msg) {
        var container = document.getElementById('gesture-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'gesture-toast-container';
            container.style.cssText =
                'position:fixed;top:20px;left:50%;transform:translateX(-50%);' +
                'z-index:100002;pointer-events:none;display:flex;flex-direction:column;align-items:center;gap:6px;';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.style.cssText =
            'background:rgba(0,0,0,0.85);color:#fff;padding:10px 24px;border-radius:10px;' +
            'font-size:13px;white-space:nowrap;backdrop-filter:blur(8px);' +
            'border:1px solid rgba(255,255,255,0.1);' +
            'animation:gesture-toast-in 0.25s ease,gesture-toast-out 0.25s ease 1.7s forwards;';
        toast.textContent = msg;
        container.appendChild(toast);

        var toastStyle = document.getElementById('gesture-toast-style');
        if (!toastStyle) {
            toastStyle = document.createElement('style');
            toastStyle.id = 'gesture-toast-style';
            toastStyle.textContent =
                '@keyframes gesture-toast-in{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}' +
                '@keyframes gesture-toast-out{from{opacity:1}to{opacity:0}}';
            document.head.appendChild(toastStyle);
        }

        setTimeout(function() {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 2200);
    }

    function registerAction(gesture, callback) {
        if (!actionCallbacks[gesture]) {
            actionCallbacks[gesture] = [];
        }
        if (typeof callback === 'function') {
            actionCallbacks[gesture].push(callback);
        }
    }

    function setPageContext(ctx) {
        pageContext = ctx;
    }

    function stop() {
        stopHealthCheck();
        if (cameraInstance) {
            try { cameraInstance.stop(); } catch(e) {}
            cameraInstance = null;
        }
        if (videoElement && videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(function(t) { t.stop(); });
            videoElement.srcObject = null;
        }
        currentState = STATE_STOPPED;
        destroyOverlay();
        lastGesture = null;
        stableGesture = null;
        stableGestureCount = 0;
        detectionStarted = false;
        handDetectedLogged = false;
        debugCounter = 0;
        lastResultsTime = 0;
        lastProcessTime = 0;

        var toastContainer = document.getElementById('gesture-toast-container');
        if (toastContainer && toastContainer.parentNode) {
            toastContainer.parentNode.removeChild(toastContainer);
        }
        if (guideEl && guideEl.parentNode) {
            guideEl.parentNode.removeChild(guideEl);
            guideEl = null;
        }

        showToast('手势交互已关闭');
    }

    function isRunning() {
        return currentState === STATE_RUNNING;
    }

    function showGuideAgain() {
        guideShown = false;
        try { localStorage.removeItem('gesture_guide_shown'); } catch(e) {}
        showGuide();
    }

    return {
        init: init,
        stop: stop,
        isRunning: isRunning,
        registerAction: registerAction,
        setPageContext: setPageContext,
        showGuide: showGuideAgain,
        GESTURE_NAMES: GESTURE_NAMES
    };
})();
