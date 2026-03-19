# 📡 KiRePa Wi-Fi Hotspot System

A full-stack Wi-Fi hotspot management system built with Django. Customers purchase data plans via M-Pesa, receive voucher codes via SMS, and connect to the internet. Includes a Kopa (data borrowing) feature and a reward points system.

> Built and maintained by [@patomurgong](https://github.com/patomurgong)

---

## 🚀 Live Features

| Feature | Description |
|---|---|
| 💳 M-Pesa Payments | STK Push via Safaricom Daraja API |
| 🎫 Voucher System | Auto-generated codes sent via SMS after payment |
| 📱 OTP Verification | SMS-based OTP for all sensitive actions |
| 🤝 Kopa (Borrow Data) | Borrow data now, repay on next purchase |
| ⭐ Reward Points | Earn 1 point per 10 Ksh spent, redeem for free data |
| 🔐 Admin Dashboard | Revenue charts, customer stats, transaction logs |
| 📊 Sparkline Charts | 7-day trends for revenue, customers, vouchers |

---

## 🖥️ Screenshots

### Hotspot Portal (Customer View)
The customer-facing portal where users purchase plans, enter vouchers, check balance, Kopa data, and redeem points.

### Admin Dashboard
Dark-themed admin panel with revenue charts, transaction history, Kopa management, and points ledger.

---

## 🛠️ Tech Stack

- **Backend**: Django 5.x + Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **Cache**: Redis (for OTP storage)
- **Payments**: Safaricom M-Pesa Daraja API (STK Push)
- **SMS**: Africa's Talking API
- **Frontend**: Vanilla HTML/CSS/JS (single file portal)
- **Admin**: Django Admin with custom dark-mode sidebar

---

## ⚙️ Requirements

Before you begin, make sure you have:

- Python 3.10+
- Git
- Redis server running locally
- Africa's Talking account (for SMS)
- Safaricom Daraja account (for M-Pesa)

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/patomurgong/final-hotspot-system.git
cd final-hotspot-system
```

### 2. Create a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Create a file called `.env` in the root of the project folder:

```env
SECRET_KEY=your-django-secret-key-here
DEBUG=True
NGROK_URL=https://your-ngrok-url.ngrok-free.app
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=your-africa's-talking-api-key
AFRICASTALKING_SENDER_ID=KIREPA
REDIS_URL=redis://127.0.0.1:6379/0
```

> ⚠️ Never commit your `.env` file to GitHub. It is already in `.gitignore`.

### 5. Run database migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create an admin user

```bash
python manage.py createsuperuser
```

### 7. Start Redis (in a separate terminal)

```bash
# Windows (if installed as a service, it may already be running)
redis-server

# Or start it from where you installed it
```

### 8. Start the development server

```bash
python manage.py runserver 0.0.0.0:8002
```

---

## 🌐 Accessing the System

| URL | Description |
|---|---|
| `http://127.0.0.1:8002/` | Customer hotspot portal |
| `http://127.0.0.1:8002/admin/` | Admin dashboard |
| `http://127.0.0.1:8002/api/` | REST API root |

---

## 📡 API Endpoints

### Plans
```
GET  /api/plans/                    — List all active plans
```

### Vouchers
```
POST /api/voucher/enter/            — Submit phone + voucher code (sends OTP)
POST /api/voucher/activate/         — Verify OTP and activate voucher
POST /api/voucher/lookup/           — Look up vouchers by phone (sends OTP)
POST /api/voucher/check-balance/    — Check remaining data balance
```

### M-Pesa Payments
```
POST /api/initiate-mpesa-payment/   — Trigger STK Push to customer phone
POST /api/mpesa/callback/           — Safaricom callback (auto creates voucher)
GET  /api/mpesa/webhook-health/     — Check if callback URL is reachable
```

### OTP
```
POST /api/otp/send/                 — Send OTP to phone
POST /api/otp/verify/               — Verify OTP code
```

### Kopa (Data Borrowing)
```
POST /api/kopa/check/               — Check eligibility and outstanding balance
POST /api/kopa/request/             — Request to borrow data (sends OTP)
POST /api/kopa/confirm/             — Verify OTP and issue Kopa voucher
```

### Reward Points
```
POST /api/points/check/             — Fetch points balance and history
POST /api/points/redeem/            — Initiate redemption (sends OTP)
POST /api/points/redeem/confirm/    — Verify OTP and issue free data voucher
```

---

## 💰 M-Pesa Setup

### Sandbox (Testing)
The project is pre-configured with Safaricom sandbox credentials. To test:

1. Go to [developer.safaricom.co.ke](https://developer.safaricom.co.ke)
2. Use the STK Push simulator to simulate payments
3. Expose your local server with ngrok:

```bash
ngrok http 8002
```

4. Update `NGROK_URL` in your `.env` file with the new ngrok URL
5. Restart the server

### Production
Update `settings.py` with your production credentials:

```python
MPESA_CONSUMER_KEY    = 'your-production-key'
MPESA_CONSUMER_SECRET = 'your-production-secret'
MPESA_PASSKEY         = 'your-production-passkey'
MPESA_BUSINESS_SHORTCODE = 'your-paybill-or-till'
```

Change sandbox URLs to production in `views.py`:
```python
auth_url     = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
stk_push_url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
```

---

## ⭐ Reward Points System

| Action | Points |
|---|---|
| Spend 10 Ksh | Earn 1 point |
| Spend 100 Ksh | Earn 10 points |
| Spend 500 Ksh | Earn 50 points |

**Redemption tiers:**

| Points | Free Data | Valid For |
|---|---|---|
| 50 pts | 50 MB | 6 hours |
| 100 pts | 150 MB | 12 hours |
| 200 pts | 400 MB | 24 hours |
| 500 pts | 1 GB | 48 hours |

Points are awarded automatically on every successful M-Pesa payment.

---

## 🤝 Kopa (Data Borrowing)

Customers can borrow data and repay on their next purchase.

**Eligibility (based on spending history):**

| Total Spent | Kopa Limit |
|---|---|
| 50 – 199 Ksh | 10 Ksh package (50 MB) |
| 200 – 499 Ksh | 20 Ksh package (100 MB) |
| 500+ Ksh | 50 Ksh package (250 MB) |

Kopa is automatically repaid when the customer makes their next M-Pesa payment.

---

## 🗄️ Database Models

| Model | Purpose |
|---|---|
| `HotspotPlan` | Wi-Fi plans (price, data, validity) |
| `Voucher` | Generated voucher codes |
| `MpesaTransaction` | Payment records |
| `HotspotCustomer` | Customer profiles |
| `KopaTransaction` | Borrow records |
| `CustomerPoints` | Points balances |
| `PointsTransaction` | Points earn/redeem ledger |
| `OTP` | OTP verification records |

---

## 📁 Project Structure

```
final-hotspot-system/
├── finalHotspot/
│   ├── settings.py         — Django settings
│   ├── urls.py             — Main URL config
│   └── wsgi.py
├── hotspot_api/
│   ├── models.py           — All database models
│   ├── views.py            — Main API views + M-Pesa
│   ├── kopa_views.py       — Kopa feature endpoints
│   ├── points_views.py     — Points feature endpoints
│   ├── admin.py            — Custom admin panels
│   ├── middleware.py       — Custom admin sidebar
│   ├── signals.py          — Auto-credit customer on payment
│   ├── sms_utils.py        — Africa's Talking SMS helper
│   ├── serializers.py      — DRF serializers
│   └── urls.py             — API URL routing
├── index.html              — Customer hotspot portal
├── manage.py
├── requirements.txt
└── .env                    — Your secrets (not committed)
```

---

## 🚀 Deployment

To deploy for real users, consider:

- **[Railway](https://railway.app)** — Easy Django deployment with Redis and PostgreSQL add-ons
- **[Render](https://render.com)** — Free tier available for Django apps
- **[PythonAnywhere](https://pythonanywhere.com)** — Beginner-friendly Django hosting

For any deployment, you will need to:
1. Switch to PostgreSQL database
2. Set `DEBUG=False`
3. Configure `ALLOWED_HOSTS` with your domain
4. Use a real ngrok URL or set up a fixed domain for M-Pesa callbacks

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to your branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 📞 Support

For help setting up or using this system:
- Open a [GitHub Issue](https://github.com/patomurgong/final-hotspot-system/issues)
- Call: **0792701147**

---

*Built with ❤️ for KiRePa Wi-Fi*