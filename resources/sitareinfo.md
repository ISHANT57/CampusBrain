# Sitare University — Complete Information Reference

Source: extracted from the Sitare University website codebase (`src/pages/*.tsx`, `src/data/*.ts`, `supabase/functions/chat/knowledge-base.ts`). This file exists for RAG ingestion — every fact the site currently contains is included, organized by topic. Student personally-identifiable information (names, phone numbers, personal emails, DOB from `src/data/students.ts`) is deliberately excluded; only aggregate counts already published elsewhere on the site are included. Content explicitly marked as placeholder on the live site is flagged as such, not presented as fact.

---

## 1. About & Mission

- Program name: Sitare University Program.
- Tagline/description: "World-class Computer Science education for bright students from economically disadvantaged backgrounds."
- Founded by Dr. Amit Singhal in 2022 to provide world-class Computer Science education to talented students from underprivileged backgrounds, completely free of cost.
- Mission statement: leaders from Silicon Valley, top American and European institutions, industry leaders, and venture capitalists came together to build a new University Program focused on Computer Science.
- Vision: "One of the best Computer Science educational institutes in India by 2030."

### Batch history
- First batch: started 2022, with 23–24 students (both figures appear on different site pages).
- Second batch: admitted 2023, 44 students.
- Third batch: admitted 2024, 158–160 students (both figures appear on different pages).
- Intent to gradually increase to around 1,000 admissions per year by 2030.
- Selection basis: JEE Mains performance plus an interview.
- Current community (as of the "Who We Are" page): approximately 220 students spanning the first three years.
- Almost all students benefit from a full 100% scholarship (tuition, hostel, and mess fees included).
- Currently operating out of SRMU Lucknow (temporary, pending the new Dewas campus).
- Nearly every student secures a paid summer internship annually, predominantly at cutting-edge startups.

### Five specialized focus areas taught
1. **Artificial Intelligence** — Machine Learning, Computer Vision, Natural Language Processing, Deep Learning.
2. **Systems** — Cloud Computing, Operating Systems, Computer Networks, Data Management, the Modern Internet.
3. **Human-Computer Interaction** — iOS and Android Development, HCI Design, Computer Graphics and Imaging, Web Applications.
4. **Data Science** — data gathering, data quality, data pipelines, ML data usage, data processing, data visualization.
5. **Computer Security** — Authentication, System Security, Network Security, Code Security, Privacy and Policy.

### Curriculum overview by year (from About page)
- Year 1: Python, Math, Data Structures, English Communication.
- Year 2: Algorithms, Java, Systems, Databases/IR, Machine Learning.
- Year 3: Frontend, Systems, more Machine Learning, alongside Hands-on Projects and Problem Solving.
- Year 4: spent in industry (paid internships start from the first summer).

### New campus
- Sitare University will be established near Indore as a full Private State University under the Madhya Pradesh Private University Act.
- Construction has started on a 38-acre site near Dewas, on the Bhopal-Indore highway.
- Target move-in dates vary by page: "August 2027" (About page), "September 2026" (Who We Are page), "July 2028" (Admissions FAQ) — treat as approximate/inconsistent across the site, not a confirmed single date.
- For now, operations are based in Lucknow, at partner university Shri (Sri) Ramswaroop Memorial University (SRMU).
- The intent to establish Sitare University in Madhya Pradesh was announced by Dr. Mohan Yadav (Hon. Chief Minister, Government of Madhya Pradesh) and Smt. Yashodhara Raje Scindia (Hon. Minister for Sports and Youth Welfare, Technical Education, Skill Development and Employment, Government of Madhya Pradesh), alongside Founder Dr. Amit Singhal.

### Sitare Foundation (parent organization)
- Established in 2016 by Dr. Amit Singhal and Mrs. Shilpa Singhal.
- Goal: empower 50,000 bright underprivileged students through education by 2050.
- Initially collaborated with schools in four Indian cities to provide free education.
- By 2021, the founders conceptualized Sitare University Program, recognizing the need for high-quality CS education.
- In 2022, the university opened in partnership with Shri Ramswaroop Memorial University, offering a BTech in Computer Science to an inaugural batch of 23 students.

---

## 2. Admissions

### Key dates (2026 cycle)
- Application Opens: 20th April 2026.
- Application Deadline: 31st July 2026 (site text also renders as "31th July, 2026").
- Results: 1st week of July 2026.
- Academic session commences: 18th August 2026.
- Students must report to the Lucknow campus: 17th August 2026.
- Apply online at: admissions.sitare.org.

### Eligibility
- Designed primarily for academically strong students from families earning ₹3 lakh or less per year (fully free). Families earning up to ₹9 lakh per year are also welcome (with reduced scholarship).
- Must appear for JEE Mains 2026; a percentile of 85 or above is generally expected.
- Must demonstrate strong academic performance in Class 10 and Class 12.
- Sitare University admits up to 120 students each year.

### Required application documents
- Applicant's passport-size photo (JPG/JPEG/PNG, max 2 MB).
- Aadhaar Card front and back (combined PDF).
- Parents' 2026 income certificate (PDF).
- Class 10 marksheet (PDF).
- Class 12 marksheet (PDF).
- JEE Mains 2026 scorecard (PDF).

### Selection process
Shortlisted candidates undergo a video interview; Sitare also conducts a background check to verify family income details.

### Courses offered
Currently only one program: B.Tech in Computer Science.

### Where classes are held
Currently at Shri Ramswaroop Memorial University (SRMU), Lucknow — a recognised university that awards the degree. Once Sitare's own Dewas campus is operational, students may have the option to transfer, subject to UGC and AICTE regulations. New campus expected ready by July 2028 (per Admissions FAQ; see date inconsistency note above).

### Scholarship & Finances
- Total program cost: ₹3,00,000 per year, fully covered by the Sitare University Scholarship for eligible students.
- Maximum any admitted student will ever pay: ₹2,00,000 per year.
- Two costs NOT covered by any scholarship: a one-time refundable caution deposit of ₹10,000 paid to SRMU at admission, and a personal laptop (~₹50,000, must be purchased by the student — not provided).
- Every admitted student receives a base scholarship of ₹1,00,000/year, plus an additional CGPA-based scholarship of up to ₹2,00,000/year.
- Additional scholarship by family income: up to ₹3 lakh income → 100%; ₹3–6 lakh → 75%; ₹6–9 lakh → 50%; above ₹9 lakh → no additional scholarship.
- Additional scholarship by CGPA: 7.5+ → full ₹2,00,000; 6.6–7.4 → ₹2,00,000 × (CGPA − 6.5) [e.g., CGPA 7.0 = ₹1,00,000]; 6.5 or below → no CGPA-based scholarship.
- To retain scholarship each year: maintain CGPA ≥ 6.5; at least 90% attendance per course; pass all subjects each semester; follow the Student Code of Conduct; provide updated family income documentation annually.
- Year 4 is structured around a year-long paid industry internship via campus recruitment. If a paid internship is secured, CGPA-based scholarship eligibility continues; if not, the student loses the CGPA-based scholarship for that year and must pay the full ₹2,00,000 program cost.
- Change in family financial situation: contact university@sitare.org with updated documentation.

### Campus life & facilities included in program cost
On-campus hostel accommodation and meals, modern classrooms, computer labs, library access, and Wi-Fi — all included within the program cost.

### Faculty
Drawn from top institutions like the IITs and from senior industry roles.

### COCO (COding and COmmunication) program
A signature summer program held after first and second years, designed to help students (including those from Hindi-medium/government schools) bridge communication gaps.

### Admissions contact
- Email: university@sitare.org
- Phone/WhatsApp: +91 78499 10085
- Website: univ.sitare.org

### Marketing taglines
"Your Journey to Silicon Valley Starts Here!" / "One choice today. A lifetime of difference." / "Admissions for 2026 are now open."

### Placement rate cited on Admissions page
91.3% placement rate.

---

## 3. Curriculum (full course list)

Intro copy: "The newly established Sitare University Program has unveiled an innovative curriculum designed for the evolving demands of the 21st century. This curriculum integrates foundational Computer Science knowledge with cutting-edge fields like Artificial Intelligence, Data Science, Web Development Frameworks, and Information Retrieval. Students will engage in project-based learning, collaborative research, and internships starting from their first year."

Curriculum PDF download link: `https://univ.sitare.org/curriculum.pdf` (marked "*Subject to Modification").

Academic Life page notes the B.Tech Computer Science program is "designed by global technology leaders and faculty from Cornell and Stanford Universities."

### Mathematics
- Math 113 — Linear Algebra
- CS 119 — Calculus
- CS 103 — Mathematical Foundations of Computing
- CS 109 — Probability for Computer Science

### Communication
- LE 101 — Introduction to Communication and Ethics
- LE 102P — Book Club and Social Emotional Intelligence
- LE 103P — Communication and Book Club
- LE 300 — Economics for Computer Science

### Programming
- CS106 — Programming Methodology in Python
- CS 110 — Data Handling in Python
- CS 108A — Object Oriented Programming
- CS 108B — Advanced Object Oriented Programming
- CS 142 — Web Applications Development
- CS 147 — Human Computer Interaction

### Core and Data
- CS 105 — Introduction to Computers
- CS 161 — Data Structures and Algorithms
- CS 162 — Advanced Data Structures and Algorithms
- CS 145 — Database Management Systems
- CS 276 — Search Engines and Information Retrieval
- CS 246 — Mining Massive Datasets
- Cornell CS 305 — Creative Problem Solving

### System and Security
- CS 107 — Computer Organization and Systems
- CS 111 — Operating Systems Principles
- CS 144 — Computer Networks

### AI/ML
- CS 221 — Artificial Intelligence
- CS 229 — Machine Learning
- CS 230 — Deep Learning
- CS 231 — Applications of Deep Learning

### Projects
- CS 106P — Python Project Course
- CoCo Summer (no course code)
- CS 250 — Software Engineering Project, Including Technical Writing
- CS 251 — Machine Learning Project

### Industry
- Industry Research Project and Internship (no course code)

---

## 4. Academic Life

- Tagline: "Igniting Curiosity, Inspiring Achievement" / "Your Path to Tech Leadership Starts Here."
- Curriculum emphasizes AI, Machine Learning, Data Science, and Information Retrieval, alongside solid theoretical foundations and practical experience.
- Guided by faculty comprising industry leaders and accomplished researchers.
- Strong integration with industry via guest lectures, hands-on workshops, seminars, robust internship programs, and industry-backed projects.
- Related site pages: Curriculum (`/curriculum`), Student Projects (`/student-projects`), Student Directory (`/students`), Academic Resources (`/academic-resources`), Announcements (`/announcements`).

---

## 5. Academic Resources — Previous Year Question Papers (full itemized list)

Page description: "Semester-wise previous year question papers for Sitare University students — internal assessments, mid-semester, and end-semester exams." Organized by semester (1–5) and subject, downloadable as PDFs. Total: 44 papers across 5 semesters (Semester 6 folder exists but is currently empty — no papers yet).

### Semester 1
- **Book Club:** IA-1 2025; IA-2 2025; Mid-Semester 2025
- **Communication:** End-Semester 2024; End-Semester 2025; IA-1 2024; IA-1 2025; IA-2 2025; Mid-Semester 2025
- **ITC:** Quiz-1 2025
- **Linear Algebra:** 2024 All Papers; 2025 All Papers
- **Python:** 2024 All Papers; 2025 All Papers

### Semester 2
- **Book Club:** IA-1 2025; Mid-Semester 2025
- **Calculus:** 2025 All Papers
- **Communication:** End-Semester 2025; Mid-Semester 2025
- **DSA:** 2025 All Papers
- **MFC:** 2025 All Papers

### Semester 3
- **ADSA:** 2024 All Papers; 2025 All Papers
- **Artificial Intelligence:** 2024 All Papers; 2025 All Papers
- **DBMS:** 2024 All Papers; 2025 All Papers
- **Java (OOP):** 2024 All Papers; 2025 All Papers
- **Probability & Theory of Computation:** 2024 All Papers; 2025 All Papers

### Semester 4
- **AOOP:** 2025 All Papers; 2026 All Papers
- **COS:** 2026 All Papers; Mid-Semester 2025
- **Machine Learning:** 2026 All Papers; Mid-Semester 2025
- **MMD (Problem Solving):** Mid-Semester 2025; 2026 All Papers
- **SEIR:** 2024 All Papers; 2025 All Papers; 2026 All Papers

### Semester 5
- **Deep Learning:** 2025 All Papers
- **Operating Systems:** 2025 All Papers

All PDFs are hosted at `/assets/documents/previous-papers/sem-{N}/{subject-slug}/{file}.pdf` on the site.

---

## 6. Campus & Facilities

General Facilities page tagline: "Where Every Star Finds Its Orbit" — "Campus Experience: Where Learning Meets Living." Facility sub-pages: Hostels, Cafeteria, Auditorium, Sports, Clubs.

### Hostels
- Tagline: "Comfortable and Secure Accommodation" / "Safe, Comfortable Living for a Focused Education."
- On-campus hostels; fully furnished rooms with modern amenities, 24x7 security, high-speed internet, housekeeping services.
- Living spaces: shared double and triple room options; common areas for study, socializing, indoor games, relaxation.
- Safety: on-site wardens and medical facilities. Special care is taken of female students to ensure they can live and learn freely without fear.
- Hostel timings: entry and exit allowed between 6:00 AM and 9:00 PM.

### Cafeteria
- Tagline: "Healthy and Delicious Dining Options" / "Where Conversations Brew and Friendships Stew!"
- Cuisine variety: mix of Indian and international dishes.
- Fresh & hygienic: meals prepared with care using fresh ingredients.
- Cafeteria timings: food available all 7 days of the week at fixed timings; changes shared with students in advance.
- Described as a social hub for students to unwind and eat with friends.

### Auditorium
- Tagline: "Where Ideas and Performances Come to Life" / "Inspiring Events, Unforgettable Experiences."
- Spacious & modern: seating for several hundred people.
- Advanced AV systems: high-quality sound systems, projectors, and lighting.
- Multifunctional: academic events, student performances, conferences, guest lectures.
- Booking: contact the administrative office.

### Sports
- Tagline: "Play, Compete, and Thrive" / "Unleash Your Potential On and Off the Field."
- Outdoor facilities: well-maintained fields for Football, Basketball, Cricket, and Athletics.
- Indoor courts: Badminton, Table Tennis, Chess.
- Recreational activities encourage teamwork, leadership, healthy lifestyle.
- Sports facility timings: outdoor fields and indoor courts available all throughout the day.
- Sports Day photos referenced on site: volleyball court, volleyball medal ceremony, sports day trophy.

---

## 7. Clubs

Clubs page tagline: "Explore Your Passion, Build Lifelong Connections" / "Where Passion Meets Purpose."

Full list of student clubs:
1. **AI Club** — "Innovating with AI Enthusiasts"
2. **Coding Club** — "Where Ideas Code into Reality"
3. **Chess Club** — "Every Move Matters"
4. **Debate Club** — "Where Words Shape the World"
5. **Founder's Forum** — "Where Entrepreneurs Converge"
6. **Music Club** — "Uniting Passionate Music Lovers"
7. **Movie Club** — "Where Every Frame Tells a Story"
8. **Media Cell** — "Where Stories Come to Life"
9. **Sports Club** — "For the Love of the Game"
10. **Yoga Club** — "Where Body and Spirit Unite"

Events page describes clubs as "launchpads for your boldest ideas" spanning tech, art, music, and social change; and describes sports as building "champions" through competition and camaraderie. Events page tagline: "Stars in Motions, Legends in the Making" and closing line: "At Sitare, we don't just follow the path, we create it."

---

## 8. Placements

### Headline placement stats
- Top CTC: ₹53 LPA
- Average CTC: ₹12 LPA
- Placement Percentage: 91.3%

Note: the `/internship-one-year` page cites slightly different figures for that specific track — Top CTC ₹21 LPA, Average CTC ₹11 LPA, Placement Percentage 91.3% — the site presents these as distinct per-page stats for the 4th-year internship track specifically, not necessarily contradictory since they refer to different cohorts/programs.

### Three-Tier Internship Program
1. **1st Year — "Igniting Your North Star":** Starts with CoCo Summer of Fun, an intensive program sharpening coding and communication skills, bridging learning and real-world application.
2. **2nd Year — "Crafting Your Constellation":** Internship becomes the foundation of professional growth; students refine skills and build resilience.
3. **3rd Year — "A Year in the Orbit of Excellence":** Exclusive 12-month internship with startups in India and Silicon Valley, USA.

Placements page closing quote: "At Sitare, your internship journey is not just a passage, it's an odyssey. With every step, we equip you with the tools, connections, and experiences to emerge as a leader poised to redefine the horizon. The stars are within your reach, let Sitare guide your ascent."

### Hiring / Industry Partners (companies students have interned/placed with)
A79, Ambient Security, AutoNxt, Beans.ai, Chalo, Chai Point, Delhivery, Digii, DriveU, FirstHive, GenePath, Glean, GOQii, Hiration, Indihood, InMobi, Inventus Capital, IoT Research Labs, KlearNow, Kloudle, LendingKart, Mathisys, Moglix, Niyo, OTO Capital, Proshort, ScaleNut, SkyRoot, SuperTails, Tracxn, Trademo, Yulu, Zeni, ZingHR.

### Placed Students — Success Stories (21 real students; hometown, company, family income multiplier)
Page states: "21 students, 21 journeys."

| Name | Hometown | Company | Income Multiplier |
|---|---|---|---|
| Animesh Awasthi | Amethi, Uttar Pradesh | Chalo | 8x |
| Ankita Pancholi | Jaipur, Rajasthan | Proshort | 6x |
| Anmol Kumar | Faridabad, Haryana | Beans | 17x |
| Ashutosh Kumar | Palamu, Jharkhand | Delhivery | 4x |
| Bharat Suthar | Jodhpur, Rajasthan | InMobi | 6x |
| Deependra Shukla | Prayagraj, Uttar Pradesh | Ambient | 17x |
| Divyansh Mishra | Mirzapur, Uttar Pradesh | Delhivery | 25x |
| Kirtan Khichi | Rajsamand, Rajasthan | KlearNow | 10x |
| Nagmani Kumar | Sitamarhi, Bihar | Indihood | 6.5x |
| Narayan Jat | Rajsamand, Rajasthan | Beans | 15x |
| Narendra Singh | Jodhpur, Rajasthan | InMobi | 12x |
| Pankaj Yadav | Gorakhpur, Uttar Pradesh | KlearNow | 6.5x |
| Ranjan Singh | Kishanganj, Bihar | KlearNow | 6x |
| Raushan Kumar | Bhagalpur, Bihar | AutoNxt | 21x |
| Shadab Raza | Pilibhit, Uttar Pradesh | FirstHive | 9x |
| Shekhar Shrivas | Niwari, Madhya Pradesh | Beans | 10x |
| Shivam Kumar | Nawada, Bihar | KlearNow | 11.5x |
| Shravan Ram | Jodhpur, Rajasthan | Ambient | 8.5x |
| Sonal Kumari | Patna, Bihar | InMobi | 16x |
| Suraj Kumar Prajapati | Mirzapur, Uttar Pradesh | KlearNow | 8.5x |
| Vidya Bharti | Tekari, Bihar | KlearNow | 8.5x |

### Internship Programs (detail pages)

**12-Month Industry Internship (`/internship-one-year`, 4th year):**
- Stats: Top CTC 21 LPA, Average CTC 11 LPA, Placement Percentage 91.3%.
- "Full-Year Immersion: 4th Year Internship Experience" — students dive into complex projects, develop professional skills, contribute meaningfully to teams.
- Highlights: Industry Placement Options (MNCs, research labs, startups — product development, R&D, data analysis); Commitment for Impact (full team integration); Why a Year-Long Internship (professional network, deeper field understanding, sustained employability).
- Process: Students apply through the Placement Office, which assists throughout.

**3-Month Summer Internship (`/internship-three-month`, 1st & 2nd year):**
- Tagline: "Building Foundations with Summer Internships" / "Building Real-World Skills from Year One."
- Purpose: bridges classroom learning and industry practice.
- Internship opportunities: software development, data science, product design, research, etc., via partner organizations.
- Student Support: resume workshops, mock interviews, personalized faculty mentor guidance.

**CoCo Summer of Fun (`/coco-summer-of-fun`):**
- Tagline: "Three-Month Coding and Communication Focused Industry Readiness Program!"
- Purpose: bridges academics and industry expectations to make students job-ready.
- Highlights: Sharpen Problem-Solving (real-time coding challenges, hackathons, competitions); Learn From Top Professionals (guest lectures, Q&A); Certify & Network (prestigious certification, networking with peers/faculty/industry leaders).

---

## 9. Transformation Stories (real student narratives, Class of 2026)

**Divyansh Mishra** — From Pathraur, near Deepnagar, Mirzapur, Uttar Pradesh. Grew up optimizing scarce resources. Local school 5 km from home; inspired by Dr. A.P.J. Abdul Kalam and Swami Vivekananda. COVID-19 lockdown disrupted preparation (no laptop, poor internet) yet he scored 93.8% in boards and cleared JEE Main 2022. Started with no CS background; secured a placement offer in his 5th semester at a now-public hi-tech Indian startup. Credits family and Dr. Amit Singhal.

**Ankita Pancholi** — From a small village near Jaipur, Rajasthan, in a joint family of 27 members. Inspired by Dr. Amit Singhal and Mrs. Shilpa Singhal. First-year internship at Beans.ai; second-year internship at Proshort.ai (Silicon Valley-based startup) as a software development intern. Mentored by Vishal Sikka, Kiran Panesar, Sridhar Ramaswamy, Sriram Sankar, and Dr. Amit Singhal. Became the first female student at Sitare University to secure a job, earning over ₹1 million (10 lakh) INR annually at Proshort.ai.

**Shravan Ram** — From Guda Bishnoiyan, near Jodhpur, Rajasthan; family of seven, father earned ₹12,000/month. Selected by Sitare Foundation in Grade 7. Moved from government school to English-medium education at Euro International School, Jodhpur; completed Grade 12 at Kids Club School, Jaipur (under Sitare Foundation). Interned at Trademo (Gurugram) and Glean (Bengaluru). Secured an offer from Ambient Security.ai (US-based cybersecurity firm). Credits Dr. Amit Singhal, Mrs. Shilpa Singhal, and the Sitare Team.

**Ashutosh Kumar** — From a modest middle-class family in Palamu, Jharkhand. Discovered Sitare University during COVID-19 while preparing for JEE. Interned at Moglix (Chandigarh) and InMobi (Gurgaon). By his 5th semester, secured placement at a now-public hi-tech Indian startup — household income (originally ₹3,500/month) increased 25 times.

---

## 10. Student Projects

Page tagline: "From Classroom Concepts to Real-World Impact" / "Turning Concepts into Reality: Explore, Create, Share." Projects are part of the curriculum, mixing individual and team work; faculty mentors guide students through the project lifecycle.

### Featured Projects
1. **BiteBase** — Django-based web app providing real-time info from trusted sources: contests/hackathons, job listings, breaking news. By Nagmani and team. Faculty mentor: Dr. Achal Agrawal. GitHub: github.com/nag2mani/BiteBase.
2. **Sakshatkar** — AI-powered interview platform automating HR, technical, and coding rounds with real-time feedback and analytics. By Raushan and team. Faculty mentor: Dr. Kushal Shah. GitHub: github.com/raushan22882917/sakshatkar-fr.
3. **GramAI** — AI-powered language learning platform to improve English communication skills. By Narendra and team. Faculty mentor: Dr. Achal Agrawal. GitHub: github.com/NarendraSinghChouhan/GramAi-languagelearningplatform.
4. **CityGraph** — Curated dataset of actual and heuristic (straight-line) distances between cities of India. By Kirtan and team. Faculty mentor: Dr. Kushal Shah. GitHub: github.com/sitareuniversity/classicalai/tree/main/CityGraph.
5. **Image Editor** — Flask-based web app for uploading/editing images: filters, cropping, blur, rotation, face detection, text extraction, undo-redo. By Rajat Malviya and Sandeep Kumar. Faculty mentor: Dr. Kushal Shah. GitHub: github.com/sitareuniversity/python/tree/main/Image%20Editor.

---

## 11. Events

Events page ties together Clubs and Sports under "University Life - Events & Activities." Student Life photo gallery references: orientation, group discussions, tug-of-war team-building, hands-on classroom activities (newspaper activity), medal ceremonies.

---

## 12. Alumni

Alumni page (`/alumni`) tabs: Benefits, Alumni Events, Gallery, Stay Connected.
- Illustrative benefits listed: Alumni Network Access, Career Mentorship, Invitations to University Events, Discounts on Further Programs (this specific content is marked as extrapolated/illustrative in the site's own codebase, not verbatim confirmed copy).
- "Stay Connected" section: encourages alumni to mentor current students, share job opportunities, or contribute to future scholarships. Social links provided: LinkedIn, Instagram, YouTube, and email.

---

## 13. Work With Us / Careers

- Page tagline: "Join the Mission at Sitare."
- Intro: "Sitare University Program is on a mission to revolutionize Computer Science education in India. Founded by Dr. Amit Singhal in 2022, our goal is to provide world-class education to brilliant students from economically disadvantaged backgrounds."
- How to apply: No live job board on the site — candidates are directed to email university@sitare.org for both Administrative and Academic vacancies.

### Why Work With Us
- Impactful Mission — mission-driven institution empowering underprivileged students.
- Innovative Environment — industry-focused curriculum with practical, real-world skill building.
- Collaborative Culture — work alongside educators, industry experts, diverse professionals.
- Professional Growth — ongoing professional development, cutting-edge projects and research.

### Core Values
- Excellence in Education
- Inclusivity and Diversity
- Social Impact
- Innovation and Industry Relevance
- Personalized Attention and Support

**Note on job openings:** any specific job-title listings (e.g., "Assistant Professor - Computer Science," "Teaching Assistant," "Front Office Executive") that may appear in the site's internal data are explicitly marked as illustrative placeholder data in the codebase, NOT verified real current openings. The real, confirmed process is: email university@sitare.org.

---

## 14. Announcements (placeholder status)

**Flagged as placeholder / not real content.** The site's announcements data explicitly states: "Placeholder content only... Replace with real notices as they are published; no invented factual claims." Current entries as of this extraction are all "Coming Soon" placeholders:
- "Announcements Section Coming Soon" (pinned) — dated July 15, 2026, category General.
- "Content Coming Soon" — dated July 1, 2026, category Academic.
- "Content Coming Soon" — dated June 20, 2026, category Admissions.
- "Content Coming Soon" — dated June 10, 2026, category Exams.

The Announcements page also embeds a live LinkedIn feed as a best-effort supplementary source (see Section 16 below) — this is real, genuine LinkedIn content, distinct from the placeholder announcement entries above.

**The Blog section** (`/blog`) is similarly explicit placeholder/"under construction" content (lorem-ipsum-style "Content Coming Soon" posts) — not real factual content, should not be cited as real news/events.

---

## 15. Contact Information

- General enquiries email: university@sitare.org
- Admissions enquiries email: admissions@sitare.org
- Phone / WhatsApp: +91 78499 10085
- Campus location / address: SRMCEM Campus, Lucknow - Faizabad Road, Lucknow 226 010
- Google Maps: https://maps.app.goo.gl/CQ415KrS6WkgkE26A
- LinkedIn: https://www.linkedin.com/school/sitare-university/posts/?feedView=all
- Instagram: https://www.instagram.com/sitarefdn/?hl=en
- YouTube: https://www.youtube.com/@SitareUniversity
- Website: https://univ.sitare.org
- Admissions portal: https://admissions.sitare.org/

---

## 16. LinkedIn Presence (embedded posts on the site)

The site's Announcements page embeds 15 real LinkedIn posts from Sitare University's official LinkedIn school page (`linkedin.com/school/sitare-university`) via LinkedIn's own public embed widget. Post identifiers (URNs) currently embedded:

1. urn:li:ugcPost:7305618051255672832 (video post)
2. urn:li:ugcPost:7241691424230924288 (video post)
3. urn:li:share:7478825558508847104
4. urn:li:share:7455561437080387584
5. urn:li:share:7454954072425549825
6. urn:li:share:7445756484380110848
7. urn:li:share:7372554662681505792
8. urn:li:share:7372157070353166337
9. urn:li:share:7371948058198192128
10. urn:li:share:7371416489976872960
11. urn:li:share:7368166076771176449
12. urn:li:share:7368572261613694976
13. urn:li:share:7368919701856378880
14. urn:li:share:7369307678164070400
15. urn:li:share:7354502696269221889

Note: LinkedIn's post feed itself is behind a login wall for automated access (confirmed via direct testing — both Firecrawl and generic web-fetch tools are blocked from browsing the public post listing without authentication), so this list represents only the specific posts that were manually identified and shared for embedding — it is not a complete archive of every LinkedIn post the university has made.

---

## 17. Our People (Founders, Faculty, Staff, Visiting Faculty, Advisors)

### Founders & Core Leadership
- Shilpa and Amit Singhal — Founders
- Dr. Anuja Agarwal — Founding Dean, Academics and Student Affairs
- Vishal Yadav — Director, Operations
- Siddhant Gupta — Director, Student Success

### Faculty & Staff
- Preeti Shukla — Faculty, Language and Communication
- Abhinav Mishra — Faculty, Applied Mathematics
- Dr. Surender Singh Samant — Faculty, Computer Science
- Chhavi Sharma — Faculty, Computer Science
- Subinoy Manna — Faculty, Computer Science
- Dr. Purnendu Shekhar Pandey — Faculty, Computer Science
- Ankit Mehta — Faculty, Computer Science
- Deepak Kumar — Faculty, Computer Science
- Rishabh Tripathi — Teaching Assistant, Applied Mathematics
- Shivam Rathore — Teaching Assistant, English and Communication
- Ajay Sonkar — Faculty-in-Training, Computer Science
- Riya Vithal Bangera — Teaching Assistant, Communication
- Aishwary Gautham — Teaching Assistant, English and Communication
- Sanjay Verma — Assistant Manager, Operations
- Rajat Singh — Operations Associate
- Britney Mannas — Media Intern

### Visiting Faculty
- Aniket Prabhune — Economics (Ex-Amazon)
- Dr. Dilip Kandlur — Computer Science (Ex-Google and IBM)
- Geeta Chaudhry — Computer Science (Ex-Google)
- Harsh Goel — Computer Science (Ex-Pinterest)
- Dr. Kiran Panesar — Computer Science (CTO, Ambient Security)
- Dr. Mainak Chaudhary — Computer Science
- Dr. Sonika Thakral — Computer Science (Ex-IIT Delhi)
- Mr. Sourav Choudhary — Economics
- Sudeep Gupta — Economics (CEO, Mathisys)
- Dr. Yoram Singer — Computer Science (AI Expert)

### Advisors
- Ajeet Singh — Program Advisor (Co-Founder, ThoughtSpot)
- Amit Prakash — Program Advisor, Computer Science (Co-Founder, ThoughtSpot)
- Anabel Jensen — Advisor (President, Six Seconds)
- Ash Lilani — Program Advisor (Managing Partner, SAAMA)
- Ben Gomes — Program Advisor, Computer Science (VP of Search, Google)
- Cathal Gurrin — Academic Advisor (Professor, School of Computing, Dublin City University)
- Claire Cardie — Academic Advisor (Professor, Computer Science, Cornell University)
- Kavita Bala — Academic Advisor (Dean, Cornell Bowers CIS, Cornell University)
- Krishna Bharat — Program Advisor (Distinguished Research Scientist, Google)
- Mehran Sahami — Academic Advisor (Chair, Computer Science, Stanford University)
- Neeraj Arora — Program Advisor (Managing Director, General Catalyst)
- Ravi Adusumalli — Program Advisor (Founder, Elevation Capital)
- Ricardo Baeza-Yates — Academic Advisor (Director of Research, Experimental AI, Northeastern University)
- Sameer Khuller — Academic Advisor (Chair, Computer Science, Northwestern University)
- Shashin Shah — Program Advisor (Founder, Think Investments)
- Sridhar Ramaswamy — Program Advisor (CEO, Snowflake)
- Sriram Sankar — Program Advisor (Technical Fellow, LinkedIn)
- Vibhu Mittal — Program Advisor (CTO, Inflection AI)
- Vijay Shekhar Sharma — Program Advisor (Founder, Paytm)
- Vishal Sikka — Program Advisor (Founder, Vianai)

---

## 18. Site Navigation / Structure

Top-level nav sections:
- **Academic Life** → Academic Life, Curriculum, Student Projects, Student Directory, Academic Resources
- **Announcements**
- **University Life** → Our Campus/Facilities, Hostels, Cafeteria, Auditorium; Clubs, Sports
- **Placements**
- **About Us** → About Us, Who We Are, Our People, Gallery
- **Contact Us**

Additional standalone pages not in top nav but present on the site: Admissions, Work With Us, Events, Blog, Alumni, CoCo Summer of Fun, 3-Month Internship, 1-Year Internship, Transformation Stories, Placed Students, Gallery.

---

## 19. Chatbot / AI Assistant on the Site

The site has a live "Ask Sitare" AI chatbot widget (bottom-right of every page), backed by a Supabase Edge Function that is grounded in this same knowledge base content and tries multiple LLM providers in sequence (Gemini, then Groq, then OpenRouter) for reliability. It is explicitly instructed to answer only from known site facts and to direct unanswerable questions to university@sitare.org or admissions@sitare.org rather than guessing.

---

## Important notes for downstream RAG use

- **Date inconsistencies are real and intentional to preserve**, not extraction errors: the site itself states different figures for the new campus completion date (Aug 2027 / Sept 2026 / July 2028) and different historical batch sizes (23 vs 24 students; 158 vs 160 students) across different pages. Do not silently resolve these — surface the ambiguity if asked, or cite the specific page's figure.
- **Placeholder content is explicitly flagged** (Announcements, Blog, illustrative job vacancy titles) — a RAG system should not present these as confirmed current facts.
- **No student PII is included anywhere in this file** — individual students' phone numbers, personal emails, and dates of birth exist in the site's internal student directory data but were deliberately excluded from this extraction and should not be sourced elsewhere for this purpose.
- All ₹ (INR) figures, dates, and named individuals above are as published on the site as of this extraction; treat this as a snapshot, not a live-updating source.
