import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddBox } from "./AddBox";

describe("AddBox", () => {
  it("renders input and detects magnet link", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddBox onAdd={onAdd} />);

    const input = screen.getByLabelText("Download source URI");
    expect(input).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();

    // Type magnet link
    fireEvent.change(input, {
      target: { value: "magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=test.iso" },
    });

    expect(screen.getByText("Magnet link detected")).toBeInTheDocument();

    const submitBtn = screen.getByLabelText("Add download");
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        "magnet:?xt=urn:btih:da39a3ee5e6b4b0d3255bfef95601890afd80709&dn=test.iso",
        undefined
      );
    });

    // Input should be cleared
    expect(input).toHaveValue("");
  });

  it("submits direct HTTP/HTTPS URL with custom name", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddBox onAdd={onAdd} />);

    const input = screen.getByLabelText("Download source URI");
    fireEvent.change(input, {
      target: { value: "https://example.com/archive.zip" },
    });

    expect(screen.getByText("Direct URL detected")).toBeInTheDocument();

    // Toggle custom name input
    const toggleBtn = screen.getByText("+ Optional custom filename");
    fireEvent.click(toggleBtn);

    const nameInput = screen.getByPlaceholderText("Custom file or folder name (optional)...");
    fireEvent.change(nameInput, { target: { value: "my-custom-archive.zip" } });

    const submitBtn = screen.getByLabelText("Add download");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        "https://example.com/archive.zip",
        "my-custom-archive.zip"
      );
    });
  });

  it("displays inline error on rejection", async () => {
    const onAdd = vi.fn().mockRejectedValue(new Error("Invalid link or SSRF violation"));
    render(<AddBox onAdd={onAdd} />);

    const input = screen.getByLabelText("Download source URI");
    fireEvent.change(input, {
      target: { value: "https://127.0.0.1/test" },
    });

    const submitBtn = screen.getByLabelText("Add download");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Invalid link or SSRF violation")).toBeInTheDocument();
    });
  });
});
