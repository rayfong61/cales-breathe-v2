import { Link } from "react-router-dom";
import React from 'react'
import { useAuth } from "./AuthContext";

function Footer() {
  const year = new Date().getFullYear();
  const { user } = useAuth();

  return (
    <footer id="footer" className="bg-rose-200 text-md">
      <section className="max-w-4xl mx-auto p-10 flex flex-col sm:flex-row sm:justify-between">
        <div>
          <h2 className="text-lg">Cale's Breathe</h2>
          330桃園市桃園區XXXX街XXX號X樓<br />
          Email: <a href="mailto:calesbreathe@gmail.com">calesbreathe@gmail.com</a><br />
          Phone: <a href="tel:+8869XXXXXXXX">09XXXXXXXX</a>

          <div id="socialMedia" className="flex mt-3 space-x-5">
            <a href="https://www.facebook.com/profile.php?id=100090461412955"><img src="002-facebook.png" className="h-6"></img></a>
            <a href="https://www.instagram.com/cales.breathe/"><img src="003-instagram.png" className="h-6"></img></a>
            <a href="https://line.me/R/ti/p/@696vtlkc?oat_content=url"><img src="001-line.png" className="h-6"></img></a>
            <a href="https://maps.app.goo.gl/92KRzjXYLyrDvHW99"><img src="google-maps.png" className="h-6"></img></a>

          </div>

        </div>
        <nav className="hidden md:flex flex-col gap-2" aria-label="footer">
          
          <Link className="hover:opacity-80" to="/services">服務項目</Link>
          <Link className="hover:opacity-80" to="/booking">立即預約</Link>
          {!user ? (
            <Link className="hover:opacity-80" to="/login">會員登入</Link>
          ) : (
            <Link className="hover:opacity-80" to="/account">我的帳號</Link>
          )}
        </nav>
        <div className="flex flex-col sm:gap-2 text-right">
          <p>Copyright &copy; {year}</p>
          <p>All Rights Reserved</p>
        </div>
      </section>
    </footer>
  )
}

export default Footer

