# 5-Minute Pitch & Presentation Script

*(Paced comfortably for a ~4:30–5:00 minute presentation with live dashboard walkthrough)*

---

### **[0:00 – 1:00] The Hook & The Blind Spot (The Problem)**
> *"If you look at how fraud detection works today — tools like Razorpay's Thirdwatch — they are really good at checking a single order when someone pays. They look at the card, the IP address, and the order amount, and in a split second, they tell you if that order looks safe."*
>
> *"The problem is, smart fraud groups don't just place one big obvious order anymore. They work in groups. A fraud ring will create 3 or 4 brand new accounts, place small normal-looking orders, and mix their details across the group."*
>
> *"For example, Account A shares a phone with Account B. Account B shares a payment card and promo with Account C. If you inspect any single order by itself, nothing looks wrong. And if an analyst runs a normal database search like `SELECT * FROM orders WHERE device_id = ...`, they only see two orders at a time. The third account is completely hidden because no single field links all three of them together. That's a huge gap in checking orders one by one."*

---

### **[1:00 – 2:15] The Solution: Connecting the Dots with a Graph**
> *(Switch to the live dashboard at `http://localhost:8000` and point to the Network Graph)*
>
> *"This is what Abuse-Ring Sentinel solves. Instead of looking at orders as separate rows in a spreadsheet or database, our model connects them like a web."*
>
> *"Every time two orders share anything — like the same device, the same delivery address, a promo code, or a payment card — we draw a line connecting them."*
>
> *"Look at this 3-order ring right here on the dashboard: `ord_ring1_2` in Mumbai and `ord_ring1_4` in Pune have completely different addresses, different cards, and different devices. In a normal database search, you would never connect them. But both of them connect to `ord_ring1_hub` — one through a shared device, and the other through a shared card and promo code. Sentinel follows these connections and pulls the entire ring together into one clear cluster in a fraction of a second."*
>
> *"You can immediately see how they operate: one central hub account coordinating multiple orders across different cities to avoid getting caught."*

---

### **[2:15 – 3:30] The AI Agent Breakdown**
> *(Click on the top flagged cluster in the dashboard to expand the AI Agent report)*
>
> *"Now, just finding a connected group isn't enough. A fraud analyst still has to figure out what is going on and make a quick decision. That's why we added our AI Agent."*
>
> *"We give the whole cluster's connections, account creation dates, order amounts, and KYC verification details directly to our AI Agent. The agent doesn't just give you a random risk score number — it looks into all the details and writes out a clear summary in plain, simple English."*
>
> *"Let's see what the agent wrote for this ring:
> 1. First, the **Observation** — it tells you that 3 orders totaling ₹8,609 are connected via shared promo codes, payment cards, and devices.
> 2. Then, the **Analysis** — it explains the strategy: all three accounts were created on the exact same afternoon (September 2nd), none of them completed KYC verification, and they are hopping credentials.
> 3. Next is the **Verdict** — a direct decision: `FLAGGED`.
> 4. And finally, the **Recommended Action** — telling the ops team to immediately hold all three orders before fulfillment and block the device."*
>
> *"This turns what used to take hours of manual checking into a quick 5-second review."*

---

### **[3:30 – 4:15] Solving False Positives (The Roommate & Dorm Problem)**
> *(Click on the cleared cluster row `ord_01479` / `ord_01906` or point to the dampening logic)*
>
> *"Now, anyone can build a strict system that flags everything — but if you start blocking real customers, you hurt sales and make people angry. The classic problem here is: what about roommates sharing an apartment, or coworkers ordering food from the same office Wi-Fi?"*
>
> *"Our model takes care of this by using smart dampening rules. If two accounts share an address, but one account is older and KYC-verified — like `ord_01906` right here — our system drops the connection weight by 85%."*
>
> *"When the AI Agent looks at this cluster, it sees that this is just a normal verified household in Hyderabad sharing an address. It gives a verdict of `CLEARED`, so real customers get their orders delivered without any trouble, while actual fraudsters get stopped."*

---

### **[4:15 – 5:00] The Results & Wrap-Up**
> *(Point to the Metrics Bar at the top of the dashboard)*
>
> *"When we tested Sentinel on our dataset of over 3,000 orders, it caught 100% of the fraud rings, and cut down the review workload by over 99%. Instead of an analyst having to look through 3,000 individual orders, they only have to check a handful of high-priority clusters."*
>
> *"To be completely upfront: we tested this on realistic test rings to show that the connections and AI reasoning work. In real production, this would connect directly to live graph databases and cloud storage."*
>
> *"Abuse-Ring Sentinel connects the dots between separate orders — helping fraud teams stop organized groups before items ever leave the warehouse. Thanks so much for listening, and I'd be happy to answer any questions!"*
