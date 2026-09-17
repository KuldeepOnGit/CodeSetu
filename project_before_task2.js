// ==========================================================
// CODESETU - SMART PROCUREMENT TRACKER
// Frontend connected with FastAPI + MySQL Backend
// ==========================================================

const API_URL = "http://127.0.0.1:5001";


// ==========================================================
// COMMON HELPERS
// ==========================================================

function scrollToSection(sectionId) {

    const section = document.getElementById(sectionId);

    if (section) {
        section.scrollIntoView({
            behavior: "smooth"
        });
    }
}


function showNotification(message) {

    const notification =
        document.getElementById("notification");

    const notificationText =
        document.getElementById("notificationText");

    if (notificationText) {
        notificationText.textContent = message;
    }

    if (notification) {

        notification.classList.add("show");

        setTimeout(() => {
            notification.classList.remove("show");
        }, 3000);

    } else {

        console.log(message);

    }
}


// ==========================================================
// LOGIN MODAL
// ==========================================================

function openLogin() {

    const modal =
        document.getElementById("loginModal");

    if (modal) {
        modal.classList.add("show");
    }
}


function closeLogin() {

    const modal =
        document.getElementById("loginModal");

    if (modal) {
        modal.classList.remove("show");
    }
}


// ==========================================================
// FARMER LOGIN
// Backend:
// POST /auth/login
// ==========================================================

async function loginUser() {

    const mobileInput =
        document.getElementById("mobile");

    if (!mobileInput) {
        console.error("Mobile input not found");
        return;
    }

    const mobile =
        mobileInput.value.trim();


    if (!/^\d{10}$/.test(mobile)) {

        showNotification(
            "❌ Please enter a valid 10-digit mobile number."
        );

        return;
    }


    try {

        console.log("Login Request:", {
            mobile_number: mobile
        });


        const response =
            await fetch(
                API_URL + "/auth/login",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        mobile_number: mobile
                    })
                }
            );


        const data =
            await response.json();


        console.log(
            "Login Response:",
            data
        );


        if (!response.ok) {

            throw new Error(
                data.detail ||
                data.message ||
                "Login failed"
            );

        }


        const farmer =
            data.farmer;


        if (!farmer) {

            throw new Error(
                "Farmer data not received"
            );

        }


        // ==========================================
        // SAVE LOGIN DATA
        // ==========================================

        localStorage.setItem(
            "loggedIn",
            "true"
        );


        localStorage.setItem(
            "farmerId",
            farmer.farmer_id
        );


        localStorage.setItem(
            "farmerName",
            farmer.name
        );


        localStorage.setItem(
            "farmerPhone",
            farmer.mobile_number
        );


        localStorage.setItem(
            "farmerVillage",
            farmer.village || ""
        );


        localStorage.setItem(
            "farmerDistrict",
            farmer.district || ""
        );


        // ==========================================
        // UPDATE DASHBOARD
        // ==========================================

        updateLoggedInFarmer(farmer);


        showNotification(
            "✅ Login successful! Welcome " +
            farmer.name
        );


        closeLogin();


        // Scroll to dashboard

        setTimeout(() => {

            scrollToSection(
                "dashboard"
            );

        }, 500);


    } catch (error) {

        console.error(
            "Login Error:",
            error
        );


        showNotification(
            "❌ " + error.message
        );

    }
}


// ==========================================================
// UPDATE FARMER DASHBOARD AFTER LOGIN
// ==========================================================

function updateLoggedInFarmer(farmer) {

    const farmerName =
        document.getElementById(
            "dashboardFarmerName"
        );


    const farmerId =
        document.getElementById(
            "dashboardFarmerId"
        );


    const tokenFarmerName =
        document.getElementById(
            "tokenFarmerName"
        );


    if (farmerName) {

        farmerName.textContent =
            farmer.name;

    }


    if (farmerId) {

        farmerId.textContent =
            farmer.farmer_id;

    }


    if (tokenFarmerName) {

        tokenFarmerName.value =
            farmer.name;

    }

}


// ==========================================================
// LOGOUT
// ==========================================================

function logoutFarmer() {

    localStorage.removeItem(
        "loggedIn"
    );

    localStorage.removeItem(
        "farmerId"
    );

    localStorage.removeItem(
        "farmerName"
    );

    localStorage.removeItem(
        "farmerPhone"
    );

    localStorage.removeItem(
        "farmerVillage"
    );

    localStorage.removeItem(
        "farmerDistrict"
    );


    showNotification(
        "👋 Farmer logged out successfully."
    );


    setTimeout(() => {

        location.reload();

    }, 800);

}


// ==========================================================
// LOAD SAVED LOGIN
// ==========================================================

function loadLoggedInFarmer() {

    const loggedIn =
        localStorage.getItem(
            "loggedIn"
        );


    if (loggedIn !== "true") {
        return;
    }


    const farmer = {

        farmer_id:
            localStorage.getItem(
                "farmerId"
            ),

        name:
            localStorage.getItem(
                "farmerName"
            ),

        mobile_number:
            localStorage.getItem(
                "farmerPhone"
            ),

        village:
            localStorage.getItem(
                "farmerVillage"
            ),

        district:
            localStorage.getItem(
                "farmerDistrict"
            )

    };


    if (farmer.name) {

        updateLoggedInFarmer(
            farmer
        );

    }


    const loginButton =
        document.querySelector(
            ".login-btn"
        );


    if (loginButton) {

        loginButton.textContent =
            "✓ Farmer Logged In";


        loginButton.onclick =
            function () {

                scrollToSection(
                    "dashboard"
                );

            };

    }

}


// ==========================================================
// AI WAITING TIME
// Backend:
// POST /ai/predict-waiting-time
// ==========================================================

async function getAIWaitingTime(
    centerId,
    queueSize
) {

    try {

        const validCenterId =
            String(centerId);


        const validQueueSize =
            Number(queueSize);


        if (
            !validCenterId ||
            validQueueSize < 0
        ) {

            throw new Error(
                "Invalid AI prediction input"
            );

        }


        console.log(
            "AI Prediction Request:",
            {
                center_id:
                    validCenterId,

                queue_size:
                    validQueueSize
            }
        );


        const response =
            await fetch(
                API_URL +
                "/ai/predict-waiting-time",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        center_id:
                            validCenterId,

                        queue_size:
                            validQueueSize

                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                "AI API failed: " +
                response.status
            );

        }


        const data =
            await response.json();


        console.log(
            "AI Prediction Response:",
            data
        );


        if (
            data.predicted_waiting_time_minutes
            === undefined
        ) {

            throw new Error(
                "AI waiting time not received"
            );

        }


        return Number(
            data.predicted_waiting_time_minutes
        );


    } catch (error) {

        console.error(
            "AI Waiting Time Error:",
            error
        );


        // Fallback

        return Number(queueSize) * 10;

    }

}


// ==========================================================
// TOKEN BOOKING
// Backend:
// POST /tokens
// ==========================================================

const tokenForm =
    document.getElementById(
        "tokenForm"
    );


if (tokenForm) {

    tokenForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            try {

                // ======================================
                // CHECK LOGIN
                // ======================================

                const loggedIn =
                    localStorage.getItem(
                        "loggedIn"
                    );


                const farmerId =
                    localStorage.getItem(
                        "farmerId"
                    );


                if (
                    loggedIn !== "true" ||
                    !farmerId
                ) {

                    showNotification(
                        "⚠️ Please login as a farmer first."
                    );

                    openLogin();

                    return;

                }


                // ======================================
                // GET FORM VALUES
                // ======================================

                const centerSelect =
                    document.getElementById(
                        "centerSelect"
                    );


                const cropSelect =
                    document.getElementById(
                        "cropSelect"
                    );


                const quantityInput =
                    document.getElementById(
                        "quantity"
                    );


                const bookingDate =
                    document.getElementById(
                        "bookingDate"
                    );


                const reportingTime =
                    document.getElementById(
                        "reportingTime"
                    );


                const centerId =
                    centerSelect
                        ? centerSelect.value
                        : "";


                const cropName =
                    cropSelect
                        ? cropSelect.value
                        : "";


                const quantity =
                    quantityInput
                        ? Number(
                            quantityInput.value
                        )
                        : 0;


                const date =
                    bookingDate
                        ? bookingDate.value
                        : "";


                const time =
                    reportingTime
                        ? reportingTime.value
                        : "";


                // ======================================
                // VALIDATION
                // ======================================

                if (!centerId) {

                    showNotification(
                        "⚠️ Please select a procurement center."
                    );

                    return;

                }


                if (!cropName) {

                    showNotification(
                        "⚠️ Please select a crop."
                    );

                    return;

                }


                if (
                    !quantity ||
                    quantity <= 0
                ) {

                    showNotification(
                        "⚠️ Please enter a valid quantity."
                    );

                    return;

                }


                if (!date) {

                    showNotification(
                        "⚠️ Please select booking date."
                    );

                    return;

                }


                if (!time) {

                    showNotification(
                        "⚠️ Please select reporting time."
                    );

                    return;

                }


                // ======================================
                // AI WAITING TIME
                // ======================================

                const queueSize =
                    await getQueueSize(
                        centerId
                    );


                const predictedWait =
                    await getAIWaitingTime(
                        centerId,
                        queueSize
                    );


                console.log(
                    "Predicted Wait:",
                    predictedWait
                );


                // ======================================
                // TOKEN API REQUEST
                // ======================================

                const tokenData = {

                    farmer_id:
                        farmerId,

                    center_id:
                        centerId,

                    crop_name:
                        cropName,

                    quantity:
                        quantity,

                    booking_date:
                        date,

                    reporting_time:
                        time

                };


                console.log(
                    "Token Booking Request:",
                    tokenData
                );


                const response =
                    await fetch(
                        API_URL + "/tokens",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    tokenData
                                )
                        }
                    );


                const data =
                    await response.json();


                console.log(
                    "Token Booking Response:",
                    data
                );


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        data.message ||
                        "Token booking failed"
                    );

                }


                // ======================================
                // SHOW TOKEN
                // ======================================

                showNotification(
                    "✅ Token booked successfully! " +
                    data.token_id
                );


                const heroToken =
                    document.getElementById(
                        "heroToken"
                    );


                const heroWaiting =
                    document.getElementById(
                        "heroWaiting"
                    );


                if (heroToken) {

                    heroToken.textContent =
                        data.token_id || "-";

                }


                if (heroWaiting) {

                    heroWaiting.textContent =
                        (
                            data.predicted_waiting_time ??
                            predictedWait ??
                            0
                        ) + " Min";

                }


                // ======================================
                // UPDATE TOKEN RESULT
                // ======================================

                displayBookedToken(
                    data
                );


            } catch (error) {

                console.error(
                    "Token Booking Error:",
                    error
                );


                showNotification(
                    "❌ " + error.message
                );

            }

        }
    );

}


// ==========================================================
// GET QUEUE SIZE
// ==========================================================

async function getQueueSize(centerId) {

    try {

        const response =
            await fetch(
                API_URL +
                "/queue/" +
                encodeURIComponent(
                    centerId
                )
            );


        if (!response.ok) {

            throw new Error(
                "Queue API failed"
            );

        }


        const data =
            await response.json();


        if (Array.isArray(data)) {

            return data.length;

        }


        if (
            data &&
            typeof data.queue_size !==
            "undefined"
        ) {

            return Number(
                data.queue_size
            );

        }


        return 0;


    } catch (error) {

        console.error(
            "Queue Size Error:",
            error
        );


        return 0;

    }

}


// ==========================================================
// DISPLAY BOOKED TOKEN
// ==========================================================

function displayBookedToken(data) {

    console.log(
        "Displaying booked token:",
        data
    );


    const tokenResult =
        document.getElementById(
            "tokenResult"
        );


    if (tokenResult) {

        tokenResult.style.display =
            "block";

    }


    const resultToken =
        document.getElementById(
            "resultToken"
        );


    const resultQueue =
        document.getElementById(
            "resultQueue"
        );


    const resultWaiting =
        document.getElementById(
            "resultWaiting"
        );


    const resultStatus =
        document.getElementById(
            "resultStatus"
        );


    if (resultToken) {

        resultToken.textContent =
            data.token_id || "-";

    }


    if (resultQueue) {

        resultQueue.textContent =
            data.queue_position ?? "-";

    }


    if (resultWaiting) {

        resultWaiting.textContent =
            (
                data.predicted_waiting_time ??
                "-"
            ) + " Min";

    }


    if (resultStatus) {

        resultStatus.textContent =
            data.status || "Scheduled";

    }

}
// ==========================================================
// UPDATE DASHBOARD WITH TOKEN
// ==========================================================

function updateDashboardWithToken(data) {

    const elements = {

        name:
            document.getElementById(
                "dashboardFarmerName"
            ),

        farmerId:
            document.getElementById(
                "dashboardFarmerId"
            ),

        token:
            document.getElementById(
                "dashboardToken"
            ),

        tokenTime:
            document.getElementById(
                "dashboardTokenTime"
            ),

        waiting:
            document.getElementById(
                "dashboardWaiting"
            ),

        status:
            document.getElementById(
                "dashboardStatus"
            ),

        crop:
            document.getElementById(
                "dashboardCrop"
            ),

        queue:
            document.getElementById(
                "dashboardQueue"
            )
    };


    // Farmer Name
    if (elements.name) {

        elements.name.textContent =
            data.farmer || "-";
    }


    // Farmer ID
    if (elements.farmerId) {

        elements.farmerId.textContent =
            localStorage.getItem(
                "farmerId"
            ) || "-";
    }


    // Token
    if (elements.token) {

        elements.token.textContent =
            data.token || "-";
    }


    // Reporting Time
    if (elements.tokenTime) {

        elements.tokenTime.textContent =
            data.reporting || "-";
    }


    // Waiting Time
    if (elements.waiting) {

        elements.waiting.textContent =
            data.waiting !== undefined
                ? data.waiting + " Min"
                : "-";
    }


    // Status
    if (elements.status) {

        elements.status.textContent =
            data.status || "-";
    }


    // Crop + Quantity
    if (elements.crop) {

        elements.crop.textContent =
            data.crop
                ? data.crop +
                  " • " +
                  data.quantity +
                  " Quintal"
                : "-";
    }


    // Queue Position
    if (elements.queue) {

        elements.queue.textContent =
            data.queue !== undefined
                ? data.queue
                : "-";
    }


    // Hero Token
    const heroToken =
        document.getElementById(
            "heroToken"
        );

    if (heroToken) {

        heroToken.textContent =
            data.token || "-";
    }


    // Hero Waiting Time
    const heroWaiting =
        document.getElementById(
            "heroWaiting"
        );

    if (heroWaiting) {

        heroWaiting.textContent =
            data.waiting !== undefined
                ? data.waiting + " Min"
                : "-";
    }


    console.log(
        "✅ Dashboard updated:",
        data
    );
}


// ==========================================================
// CHECK TOKEN STATUS
// ==========================================================

async function checkTokenStatus() {

    const input =
        document.getElementById(
            "statusTokenInput"
        );


    if (!input) {

        console.error(
            "❌ statusTokenInput not found"
        );

        return;
    }


    const tokenId =
        input.value
            .trim()
            .toUpperCase();


    if (!tokenId) {

        alert(
            "Please enter your token ID"
        );

        return;
    }


    if (!tokenId.startsWith("KSN-")) {

        alert(
            "Please enter a valid Token ID like KSN-1027"
        );

        return;
    }


    try {

        const response =
            await fetch(
                API_URL +
                "/tokens/" +
                encodeURIComponent(
                    tokenId
                )
            );


        const data =
            await response.json();


        console.log(
            "Token Status:",
            data
        );


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Token not found"
            );
        }


        // ==========================================
        // SHOW RESULT CARD
        // ==========================================

        const statusResult =
            document.getElementById(
                "statusResult"
            );


        if (statusResult) {

            statusResult.style.display =
                "block";
        }


        // ==========================================
        // BASIC STATUS INFORMATION
        // ==========================================

        const statusTokenTitle =
            document.getElementById(
                "statusTokenTitle"
            );


        const statusFarmerId =
            document.getElementById(
                "statusFarmerId"
            );


        const statusQueue =
            document.getElementById(
                "statusQueue"
            );


        const statusProcurement =
            document.getElementById(
                "statusProcurement"
            );


        const statusBadge =
            document.getElementById(
                "statusBadge"
            );


        if (statusTokenTitle) {

            statusTokenTitle.textContent =
                "Token " +
                data.token_id;
        }


        if (statusFarmerId) {

            statusFarmerId.textContent =
                data.farmer_id || "-";
        }


        if (statusQueue) {

            statusQueue.textContent =
                data.queue_position ??
                "-";
        }


        if (statusProcurement) {

            statusProcurement.textContent =
                data.status || "-";
        }


        if (statusBadge) {

            statusBadge.textContent =
                data.status ||
                "Unknown";
        }


        // ==========================================
        // TOKEN DETAILS
        // ==========================================

        const statusToken =
            document.getElementById(
                "statusToken"
            );


        const statusCrop =
            document.getElementById(
                "statusCrop"
            );


        const statusQuantity =
            document.getElementById(
                "statusQuantity"
            );


        if (statusToken) {

            statusToken.textContent =
                data.token_id || "-";
        }


        if (statusCrop) {

            statusCrop.textContent =
                data.crop_name || "-";
        }


        if (statusQuantity) {

            statusQuantity.textContent =
                data.quantity !== undefined
                    ? data.quantity +
                      " Quintal"
                    : "-";
        }


        console.log(
            "✅ Token status loaded successfully"
        );


    } catch (error) {

        console.error(
            "Token Status Error:",
            error
        );


        alert(
            "❌ " +
            error.message
        );
    }
}
// ==========================================================
// SELECT CENTER
// ==========================================================

function selectCenter(centerId) {

    const centerSelect =
        document.getElementById("tokenCenter");

    if (centerSelect) {
        centerSelect.value = String(centerId);
    }

    scrollToSection("token");

    showNotification(
        "📍 Center selected: " + centerId
    );
}


// ==========================================================
// CENTER DATA LOAD
// ==========================================================

async function loadCenters() {

    try {

        const response =
            await fetch(
                API_URL + "/centers"
            );

        if (!response.ok) {
            throw new Error(
                "Centers API failed"
            );
        }

        const centers =
            await response.json();

        console.log(
            "Centers:",
            centers
        );

        return centers;

    } catch (error) {

        console.error(
            "Centers Error:",
            error
        );

        return [];
    }
}


// ==========================================================
// LOAD LAST TOKEN
// ==========================================================

async function loadLastTokenToDashboard() {

    const tokenId =
        localStorage.getItem(
            "tokenNumber"
        );

    if (!tokenId) {
        return;
    }

    try {

        const response =
            await fetch(
                API_URL +
                "/tokens/" +
                encodeURIComponent(tokenId)
            );

        if (!response.ok) {
            return;
        }

        const data =
            await response.json();

        updateDashboardWithToken({
            token:
                data.token_id,

            farmer:
                localStorage.getItem(
                    "farmerName"
                ) || "-",

            crop:
                data.crop_name,

            quantity:
                data.quantity,

            center:
                data.center_id,

            waiting:
                data.predicted_waiting_time,

            queue:
                data.queue_position,

            reporting:
                data.reporting_time,

            status:
                data.status
        });

    } catch (error) {

        console.error(
            "Dashboard Token Error:",
            error
        );
    }
}


// ==========================================================
// ADMIN DEMO UPDATE
// ==========================================================

function updateAdmin() {

    const totalTokens =
        document.getElementById(
            "totalTokens"
        );

    const pendingTokens =
        document.getElementById(
            "pendingTokens"
        );


    if (totalTokens) {

        const current =
            parseInt(
                totalTokens.textContent
            ) || 0;

        totalTokens.textContent =
            current + 1;
    }


    if (pendingTokens) {

        const current =
            parseInt(
                pendingTokens.textContent
            ) || 0;

        pendingTokens.textContent =
            current + 1;
    }
}


// ==========================================================
// ESC KEY
// ==========================================================

document.addEventListener(
    "keydown",
    function (event) {

        if (event.key === "Escape") {
            closeLogin();
        }

    }
);


// ==========================================================
// LOGIN MODAL CLICK OUTSIDE
// ==========================================================

document.addEventListener(
    "click",
    function (event) {

        const modal =
            document.getElementById(
                "loginModal"
            );

        if (
            modal &&
            event.target === modal
        ) {

            closeLogin();
        }

    }
);


// ==========================================================
// PAGE LOAD
// ==========================================================

document.addEventListener(
    "DOMContentLoaded",
    async function () {

        console.log(
            "CodeSetu frontend loaded."
        );


        // ==========================================
        // LOAD SAVED FARMER
        // ==========================================

        loadLoggedInFarmer();


        // ==========================================
        // LOAD LAST TOKEN
        // ==========================================

        await loadLastTokenToDashboard();


        // ==========================================
        // SET MINIMUM BOOKING DATE
        // ==========================================

        const dateInput =
            document.getElementById(
                "tokenDate"
            );


        if (dateInput) {

            const today =
                new Date()
                    .toISOString()
                    .split("T")[0];

            dateInput.min =
                today;
        }


        // ==========================================
        // AUTO-FILL FARMER NAME
        // ==========================================

        const farmerName =
            localStorage.getItem(
                "farmerName"
            );


        const tokenFarmerName =
            document.getElementById(
                "tokenFarmerName"
            );


        if (
            farmerName &&
            tokenFarmerName
        ) {

            tokenFarmerName.value =
                farmerName;
        }

    }
);