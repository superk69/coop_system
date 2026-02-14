// script.js

// จำลองข้อมูล (Mock Data)
const mockAnnouncements = [
    { title: "แจ้งกำหนดการส่งเอกสารสหกิจ", date: "2023-10-01" },
    { title: "บริษัท ABC เปิดรับสมัครนักศึกษาฝึกงาน", date: "2023-10-05" }
];

const mockTraining = [
    { topic: "การเขียนเรซูเม่", hours: 3, status: "APPROVED" },
    { topic: "ทักษะการสัมภาษณ์งาน", hours: 3, status: "PENDING" }
];

// ฟังก์ชันจำลองการ Login
function login() {
    const roleSelect = document.getElementById("roleSelect").value;
    
    // ซ่อนหน้า Login
    document.getElementById("login-page").classList.add("hidden");
    
    // แสดง Navbar
    document.getElementById("main-navbar").classList.remove("hidden");
    
    // แสดงหน้า Dashboard ตามบทบาท
    if (roleSelect === "student") {
        document.getElementById("student-dashboard").classList.remove("hidden");
        loadStudentData();
    } else if (roleSelect === "teacher") {
        document.getElementById("teacher-dashboard").classList.remove("hidden");
    }
    
    // แสดงชื่อผู้ใช้ (จำลอง)
    document.getElementById("user-name").innerText = roleSelect === "student" ? "นศ. สมชาย ใจดี" : "อ. วิชาญ รักเรียน";
}

// ฟังก์ชันจำลองการ Logout
function logout() {
    location.reload(); // รีโหลดหน้าเพื่อกลับไปจุดเริ่มต้น
}

// โหลดข้อมูลนักศึกษาจำลอง
function loadStudentData() {
    // 1. โหลดประกาศข่าว
    const newsList = document.getElementById("news-list");
    newsList.innerHTML = ""; // ล้างค่าเก่า
    mockAnnouncements.forEach(news => {
        const item = document.createElement("div");
        item.innerHTML = `<p><strong>${news.title}</strong> <span style="color: #666; font-size: 0.9em;">(${news.date})</span></p>`;
        item.style.borderBottom = "1px solid #eee";
        newsList.appendChild(item);
    });

    // 2. โหลดประวัติการอบรม
    const trainingTable = document.getElementById("training-table-body");
    trainingTable.innerHTML = "";
    mockTraining.forEach(t => {
        let statusClass = "";
        let statusText = "";
        
        if (t.status === "APPROVED") {
            statusClass = "badge-approved";
            statusText = "อนุมัติแล้ว";
        } else {
            statusClass = "badge-pending";
            statusText = "รอตรวจสอบ";
        }

        const row = `
            <tr>
                <td>${t.topic}</td>
                <td>${t.hours}</td>
                <td><span class="badge ${statusClass}">${statusText}</span></td>
            </tr>
        `;
        trainingTable.innerHTML += row;
    });
}