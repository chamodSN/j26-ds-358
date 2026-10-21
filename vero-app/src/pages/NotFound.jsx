import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";

export default function NotFound() {
    return (
        <EmptyState
            title="This page does not exist"
            text="The link may be old or mistyped."
            action={<Link to="/" className="btn-primary">Go home</Link>}
        />
    );
}