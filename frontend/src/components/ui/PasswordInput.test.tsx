import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it} from "vitest";
import {PasswordInput} from "./PasswordInput";

describe("PasswordInput", () => {
  afterEach(cleanup);

  it("toggles password visibility without changing the value", () => {
    render(<PasswordInput aria-label="Password" defaultValue="secret123" />);
    const input = screen.getByLabelText("Password") as HTMLInputElement;

    expect(input.type).toBe("password");
    fireEvent.click(screen.getByRole("button", {name: "Show password"}));
    expect(input.type).toBe("text");
    expect(input.value).toBe("secret123");
    fireEvent.click(screen.getByRole("button", {name: "Hide password"}));
    expect(input.type).toBe("password");
  });
});
