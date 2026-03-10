import { render, screen } from "@testing-library/react";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders the headline", () => {
    render(<HomePage />);
    expect(screen.getByText("Follow the Money")).toBeInTheDocument();
  });

  it("renders the description", () => {
    render(<HomePage />);
    expect(screen.getByText(/Find your representatives/i)).toBeInTheDocument();
  });
});
