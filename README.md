# LeetCode Clone — Django + PostgreSQL

## Why This Project?

Most tutorials give you enough to get started but not enough to build something real.
The best way to learn a tech stack is to pick one ambitious goal and build toward it.

I chose to build a LeetCode-style platform because:

1. I've been solving LeetCode problems for over a year and wanted to understand how it works under the hood.
2. It involves 36+ database tables, covering complex SQL joins and real schema design.
3. The backend logic — thousands of problems, domains, submissions — is genuinely challenging.
4. It touches scaling, security, and system design concepts.


## About This Project

I am building a LeetCode-style platform from scratch to learn full stack web development the right way. Instead of following tutorials, I picked one big project and started building it end to end. This forces me to think like a real developer — handling models, views, templates, database, authentication, file uploads, and more.

I have been solving LeetCode problems for over a year. So I thought, why not build the website itself? That curiosity is what started this project.

**Tech Stack**
- Backend — Django
- Frontend — Django Templates + Bootstrap 5
- Database — PostgreSQL

---

## Development Log

---

### 04 May 2026

#### 1. Fixed Password Reset OTP Flow

The reset password feature was broken. After entering email and sending OTP, the second POST was returning `200` instead of redirecting. The root cause was that `ForgotPasswordForm` was being validated on the OTP step — but the OTP form only sends the OTP field, not email or password. So `form.is_valid()` was silently failing every time.

Fixed it by following the same session-based pattern used in `register_view`:

- On `send-otp` step — validate the full form, store email and hashed password in session
- On `verify-otp` step — only read OTP from POST, everything else comes from session
- No form validation needed on step 2

Also extracted OTP logic into a pure utility function `verify_otp()` that takes no request and just returns `(bool, message)`. Clean and reusable.

---

#### 2. Created Courses App

Added a new `courses` app to the project. Defined the `Courses` model with the following fields:

- `title`, `description`, `duration` — core fields
- `is_paid`, `price`, `rating` — business logic
- `thumbnail` — `ImageField` storing under `media/courses/thumbnails/`
- `intro_video` — `FileField` storing under `media/courses/videos/`
- `attachment` — `FileField` storing under `media/courses/attachments/`
- `created_at`, `last_updated` — auto handled by Django

Learned an important distinction today — `static/` is for files you write like CSS, JS, logos. `media/` is for uploaded content like thumbnails and videos. Never mix the two.

---

#### 3. Configured Media Files

Added media settings in `settings.py`:

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

Added media URL serving in project `urls.py` for development:

```python
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

This tells Django — whenever a request comes for `/media/anything`, go look inside `MEDIA_ROOT` and serve that file.

---

#### 4. Seed and Update Management Commands

Instead of adding courses one by one through admin, created two management commands under `courses/management/commands/`:

**`seed_courses.py`** — inserts all courses in bulk using `get_or_create` so running it multiple times does not create duplicates.

**`update_courses.py`** — updates thumbnail paths for existing courses using `.filter().update()`. Useful when you manually paste images into the media folder and want to link them to the database.

Run them like this:

```bash
python manage.py seed_courses
python manage.py update_courses
```

---

#### 5. Built Course Listing Page

Built the courses home page using Bootstrap 5 dark theme. Key design decisions:

- Image takes `16:9` aspect ratio — always consistent, never stretched
- Premium badge shows in gold color with a ★ star in top right corner of the image
- Free badge shows in blue
- Graceful fallback — if no thumbnail, shows a book icon placeholder
- Description clamped to 3 lines — keeps all cards same height
- Duration and View Course button in the card footer

Also added `{% empty %}` block — if no courses exist in database, shows a proper empty state instead of blank page.

---

#### 6. Built Base Template with Navbar

Created `base.html` with a full Bootstrap navbar:

- Top left — BashaByte logo image + brand name
- Center — Problems, Courses, Posts, Contests navigation links
- Top right — Profile icon with dropdown showing Profile, Settings, Logout

All other templates extend this base so the navbar is consistent across every page.

---

#### What I Learned Today

- Session-based OTP flow is the right pattern — store data in session on step 1, read it back on step 2
- `static/` is for your own files, `media/` is for uploaded content
- Management commands are the cleanest way to seed or update data in bulk
- File names in media folder must exactly match what is stored in the database — case sensitive, no spaces
- `get_or_create` returns `(instance, created)` — instance first, boolean second
- `render()` always returns 200, only `redirect()` returns 302 — that is normal and expected

---