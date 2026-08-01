import { Link } from "react-router-dom";
import UserMenu from "../auth/UserMenu";
import { APP_NAME } from "../../lib/constants";

export default function Navbar() {
  return (
    <nav className="navbar">
      <Link to="/dashboard" className="navbar-brand">
        <span className="navbar-logo">⚡</span>
        <span className="navbar-name">{APP_NAME}</span>
      </Link>
      <UserMenu />
    </nav>
  );
}
