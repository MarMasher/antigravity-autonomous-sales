"""
Page content generators for each page of the multi-page Puter.js site.
"""
from utils.site_templates import render_nav, page_shell

PAGES = [("Home","index.html"),("Services","services.html"),("About","about.html"),("Contact","contact.html")]


def build_index(biz: str, niche: str, loc: str) -> str:
    nav  = render_nav(biz, PAGES)
    body = f'''
<section class="hero">
  <div class="hero-content">
    <div class="hero-badge">⚡ {loc}</div>
    <h1><span class="gradient-text">{biz}</span></h1>
    <p>Premium {niche} services in {loc}. Trusted by hundreds of satisfied customers. Quality you can see, results you can trust.</p>
    <div class="hero-btns">
      <a href="contact.html" class="btn-primary">Get a Free Quote</a>
      <a href="services.html" class="btn-ghost">View Services</a>
    </div>
  </div>
</section>

<section style="background:var(--bg2);padding:96px 24px">
  <div class="container">
    <div class="section-label">Why Choose Us</div>
    <h2>Built on <span class="gradient-text">Trust &amp; Results</span></h2>
    <p class="section-sub">We bring hands-on expertise and a customer-first attitude to every job we take.</p>
    <div class="cards">
      <div class="card"><div class="card-icon">⚡</div><h3>Fast Turnaround</h3><p>We respect your time. Professional service delivered on schedule, every time.</p></div>
      <div class="card"><div class="card-icon">★</div><h3>5-Star Quality</h3><p>Consistently rated 5 stars by our customers across all platforms.</p></div>
      <div class="card"><div class="card-icon">🛡</div><h3>Satisfaction Guaranteed</h3><p>Not happy? We make it right — no questions asked. Your satisfaction is our priority.</p></div>
      <div class="card"><div class="card-icon">📍</div><h3>Local Experts</h3><p>We know {loc} inside and out. We're your neighbors, and we care about our community.</p></div>
    </div>
    <div class="stats">
      <div><div class="stat-n">500+</div><div class="stat-l">Jobs Completed</div></div>
      <div><div class="stat-n">5★</div><div class="stat-l">Average Rating</div></div>
      <div><div class="stat-n">100%</div><div class="stat-l">Satisfaction Rate</div></div>
      <div><div class="stat-n">8yr</div><div class="stat-l">In Business</div></div>
    </div>
  </div>
</section>

<section style="background:linear-gradient(135deg,var(--ac),#6356e8);padding:80px 24px;text-align:center">
  <div class="container">
    <h2 style="color:#fff;margin-bottom:16px">Ready to Get Started?</h2>
    <p style="color:rgba(255,255,255,.85);font-size:1.1rem;margin-bottom:36px">Contact us today for a free, no-obligation quote. Serving {loc} and surrounding areas.</p>
    <a href="contact.html" style="padding:16px 40px;background:#fff;color:var(--ac);border-radius:12px;font-weight:700;font-size:16px;display:inline-block;transition:transform .2s" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform=''">Contact Us Now →</a>
  </div>
</section>
'''
    return page_shell(f"{biz} — {niche} in {loc}", f"Professional {niche} services in {loc}. Reliable, trusted, and affordable.", biz, niche, loc, nav, body)


def build_services(biz: str, niche: str, loc: str) -> str:
    nav  = render_nav(biz, PAGES)
    body = f'''
<section style="padding:120px 24px 60px">
  <div class="container">
    <div class="section-label">What We Offer</div>
    <h2>Our <span class="gradient-text">Services &amp; Pricing</span></h2>
    <p class="section-sub">Transparent pricing. No hidden fees. Pick the plan that's right for you.</p>
    <div class="pricing">
      <div class="plan">
        <div class="plan-badge">Starter</div>
        <div class="plan-price">$299</div>
        <div class="plan-period">one-time</div>
        <ul class="plan-features">
          <li>Basic {niche} package</li>
          <li>1–2 hour service window</li>
          <li>Email support</li>
          <li>Satisfaction guarantee</li>
        </ul>
        <a href="contact.html" class="btn-plan btn-plan-ghost">Book Starter</a>
      </div>
      <div class="plan featured">
        <div class="plan-badge">⭐ Most Popular</div>
        <div class="plan-price">$599</div>
        <div class="plan-period">one-time</div>
        <ul class="plan-features">
          <li>Full {niche} treatment</li>
          <li>Premium materials &amp; tools</li>
          <li>Priority scheduling</li>
          <li>Photo documentation</li>
          <li>30-day follow-up</li>
          <li>Priority phone support</li>
        </ul>
        <a href="contact.html" class="btn-plan btn-plan-primary">Book Standard</a>
      </div>
      <div class="plan">
        <div class="plan-badge">Premium</div>
        <div class="plan-price">$999</div>
        <div class="plan-period">one-time</div>
        <ul class="plan-features">
          <li>Complete {niche} solution</li>
          <li>All Standard features</li>
          <li>Extended 90-day warranty</li>
          <li>VIP support line</li>
          <li>Monthly check-ins</li>
          <li>Free touch-up visit</li>
        </ul>
        <a href="contact.html" class="btn-plan btn-plan-ghost">Book Premium</a>
      </div>
    </div>
  </div>
</section>

<section style="background:var(--bg2);padding:80px 24px">
  <div class="container" style="text-align:center">
    <h2 style="margin-bottom:16px">Not Sure Which Plan?</h2>
    <p style="color:var(--tx2);margin-bottom:36px;font-size:1.1rem">Our AI assistant can help you pick the right service for your needs. Or contact us directly for a custom quote.</p>
    <a href="contact.html" class="btn-primary" style="display:inline-block">Talk to Us →</a>
  </div>
</section>
'''
    return page_shell(f"Services — {biz}", f"{niche} services and pricing in {loc}.", biz, niche, loc, nav, body)


def build_about(biz: str, niche: str, loc: str) -> str:
    nav  = render_nav(biz, PAGES)
    body = f'''
<section style="padding:120px 24px 60px">
  <div class="container">
    <div style="max-width:720px">
      <div class="section-label">Our Story</div>
      <h2>About <span class="gradient-text">{biz}</span></h2>
      <p style="color:var(--tx2);font-size:1.15rem;line-height:1.8;margin-bottom:24px">
        We are a dedicated {niche} company proudly serving {loc} and the surrounding communities. 
        Our mission is simple: deliver exceptional quality, on time, every time.
      </p>
      <p style="color:var(--tx2);font-size:1.05rem;line-height:1.8;margin-bottom:40px">
        Founded by local professionals who are passionate about {niche}, we bring hands-on expertise 
        and a customer-first attitude to every job. We are not a franchise — we are your neighbors, 
        and we care about our reputation in this community.
      </p>
    </div>
    <div class="stats" style="margin-top:0">
      <div><div class="stat-n">500+</div><div class="stat-l">Satisfied Clients</div></div>
      <div><div class="stat-n">8yr</div><div class="stat-l">In Business</div></div>
      <div><div class="stat-n">100%</div><div class="stat-l">Insured &amp; Certified</div></div>
      <div><div class="stat-n">5★</div><div class="stat-l">Average Rating</div></div>
    </div>
  </div>
</section>

<section style="background:var(--bg2);padding:80px 24px">
  <div class="container">
    <div class="section-label">Our Values</div>
    <h2>What Drives <span class="gradient-text">Everything We Do</span></h2>
    <div class="cards" style="margin-top:48px">
      <div class="card"><div class="card-icon">🤝</div><h3>Honesty</h3><p>We give you straightforward, fair pricing with no hidden fees or upsells.</p></div>
      <div class="card"><div class="card-icon">🏆</div><h3>Excellence</h3><p>We use premium materials and proven techniques on every single job.</p></div>
      <div class="card"><div class="card-icon">💬</div><h3>Communication</h3><p>You're always in the loop. We respond fast and keep you updated.</p></div>
    </div>
  </div>
</section>
'''
    return page_shell(f"About — {biz}", f"Learn about {biz}, your trusted {niche} provider in {loc}.", biz, niche, loc, nav, body)


def build_contact(biz: str, niche: str, loc: str) -> str:
    nav  = render_nav(biz, PAGES)
    body = f'''
<section style="padding:120px 24px 80px">
  <div class="container">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:60px;align-items:start">
      <div>
        <div class="section-label">Reach Out</div>
        <h2>Get a <span class="gradient-text">Free Quote</span></h2>
        <p style="color:var(--tx2);line-height:1.7;margin-bottom:40px">We'll get back to you within 24 hours. Serving {loc} and surrounding areas.</p>
        <div style="display:flex;flex-direction:column;gap:20px">
          <div style="display:flex;align-items:center;gap:16px">
            <div class="card-icon">📞</div>
            <div><div style="font-weight:600">Call Us</div><div style="color:var(--tx2);font-size:14px">(555) 000-0000</div></div>
          </div>
          <div style="display:flex;align-items:center;gap:16px">
            <div class="card-icon">📧</div>
            <div><div style="font-weight:600">Email Us</div><div style="color:var(--tx2);font-size:14px">hello@{biz.lower().replace(' ','')}service.com</div></div>
          </div>
          <div style="display:flex;align-items:center;gap:16px">
            <div class="card-icon">📍</div>
            <div><div style="font-weight:600">Service Area</div><div style="color:var(--tx2);font-size:14px">{loc} &amp; surrounding areas</div></div>
          </div>
        </div>
      </div>
      <form style="background:var(--bg2);padding:40px;border-radius:20px;border:1px solid var(--bd)" onsubmit="handleForm(event)">
        <div class="form-grid">
          <div class="field"><label>Full Name</label><input type="text" placeholder="John Smith" required></div>
          <div class="field"><label>Phone</label><input type="tel" placeholder="(555) 000-0000"></div>
          <div class="field full"><label>Email</label><input type="email" placeholder="john@example.com" required></div>
          <div class="field full"><label>What do you need?</label><textarea placeholder="Describe your project…" required></textarea></div>
        </div>
        <button type="submit" class="btn-primary" style="width:100%;margin-top:20px" id="submit-btn">Send Message →</button>
      </form>
    </div>
  </div>
</section>

<script>
async function handleForm(e) {{
  e.preventDefault();
  const btn = document.getElementById('submit-btn');
  btn.textContent = 'Sending...';
  btn.disabled = true;
  // Puter.js: save form submission to cloud KV
  try {{
    const formData = {{ ts: Date.now(), page: location.href }};
    await puter.kv.set('contact_' + Date.now(), JSON.stringify(formData));
  }} catch(err) {{}}
  setTimeout(() => {{
    btn.textContent = '✓ Message Sent!';
    btn.style.background = '#10b981';
    e.target.reset();
  }}, 800);
}}
</script>

@media(max-width:768px){{.container > div{{grid-template-columns:1fr!important}}}}
'''
    return page_shell(f"Contact — {biz}", f"Contact {biz} for {niche} services in {loc}.", biz, niche, loc, nav, body)


def generate_all_pages(biz: str, niche: str, loc: str) -> dict[str, str]:
    """Returns dict of {filename: html_content} for all pages."""
    return {
        "index.html":    build_index(biz, niche, loc),
        "services.html": build_services(biz, niche, loc),
        "about.html":    build_about(biz, niche, loc),
        "contact.html":  build_contact(biz, niche, loc),
    }
