import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";
import App from "./App.jsx";

describe("App", () => {
  it("renders header title", () => {
    const { getByText } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );
    expect(getByText("ProjectPlanning")).toBeInTheDocument();
  });
});

