class Autotune < Formula
  desc "AI-guided compiler optimization and LLVM phase-ordering doctor for C/C++ workloads"
  homepage "https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor"
  url "https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "Apache-2.0"
  head "https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor.git", branch: "main"

  depends_on "llvm"
  depends_on "python@3.11"

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install resources
    venv.pip_install_and_link buildpath
  end

  test do
    assert_match "Autotune v#{version}", shell_output("#{bin}/autotune doctor")
  end
end
