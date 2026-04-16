<template>
  <div class="flex items-center justify-center min-h-[70vh]">
    <div class="w-full max-w-md">
      <h1 class="text-2xl font-bold text-white text-center mb-6">Sign in to Agent Black Box</h1>
      <div class="flex justify-center">
        <SignIn
          :routing="'path'"
          :path="'/login'"
          :sign-up-url="'/register'"
          appearance="{}"
        />
      </div>
    </div>
  </div>
</template>
